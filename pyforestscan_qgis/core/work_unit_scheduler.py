"""Crash-safe bounded scheduler for polygon product work units."""
from __future__ import annotations
import hashlib,json,threading,time
from concurrent.futures import FIRST_COMPLETED,ThreadPoolExecutor,wait
from dataclasses import asdict,dataclass,field,replace
from datetime import datetime,timezone
from pathlib import Path
from .source_aware_processing import WorkUnit
from .atomic_state import atomic_write_json,remove_invalid_temporaries

DETERMINISTIC_CODES={"HAG_COLLINEAR_INPUT","EMPTY_SPATIAL_READ","HAG_INSUFFICIENT_GROUND","HAG_INVALID_GEOMETRY"}
NATIVE_CRASH_CODE="NATIVE_BACKEND_CRASH"

@dataclass(frozen=True)
class WorkUnitResult:
    work_unit_id:str;status:str;output_path:Path|None=None;attempt_count:int=1;runtime_seconds:float=0;error_code:str="";message:str="";checksum:str="";metrics:dict=field(default_factory=dict)

@dataclass(frozen=True)
class SchedulerProgress:
    stage:str;completed:int;total:int;failed:int;active:int;retries:int;elapsed_seconds:float;current_units:tuple[str,...];latest_completed:str="";eta_seconds:float|None=None;attempted:int=0;pending:int=0;paused:bool=False;stop_reason:str=""
    @property
    def message(self):return f"{self.completed} complete, {self.failed} failed, {self.attempted} of {self.total} attempted, {self.pending} not started."

@dataclass(frozen=True)
class CircuitBreakerDecision:
    stop:bool=False;pause:bool=False;reason:str="";signature:str=""

class WorkFailureCircuitBreaker:
    """Stop repeated deterministic spatial failures before they consume a job."""
    def __init__(self,pause_threshold=3,stop_threshold=5,native_crash_threshold=1):
        self.pause_threshold=max(1,pause_threshold);self.stop_threshold=max(self.pause_threshold,stop_threshold);self.native_crash_threshold=max(1,native_crash_threshold);self._history=[]
    def record(self,result):
        code=result.error_code or "EXECUTION_FAILED";signature=_error_signature(result);index=_unit_index(result.work_unit_id);self._history.append((code,signature,index))
        if code==NATIVE_CRASH_CODE and sum(item[0]==code for item in self._history)>=self.native_crash_threshold:return CircuitBreakerDecision(True,False,"Processing stopped because a native LiDAR worker crashed.",signature)
        if code not in DETERMINISTIC_CODES:return CircuitBreakerDecision()
        matching=[item for item in self._history if item[:2]==(code,signature)]
        if len(matching)>=self.stop_threshold:return CircuitBreakerDecision(True,False,"Processing stopped after repeated identical ground-normalization failures.",signature)
        adjacent=_adjacent_tail(matching)
        if adjacent>=self.pause_threshold:return CircuitBreakerDecision(False,True,"Processing paused after repeated ground-normalization failures in neighboring areas.",signature)
        return CircuitBreakerDecision()
    def rebuild(self,results):
        decision=CircuitBreakerDecision()
        for result in sorted(results,key=lambda item:_unit_index(item.work_unit_id)):
            if result.status=="Failed":decision=self.record(result)
        return decision

class CheckpointStore:
    def __init__(self,folder,job_signature):self.folder=Path(folder);self.signature=job_signature;self.folder.mkdir(parents=True,exist_ok=True)
    def path(self,unit_id):return self.folder/unit_id/"status.json"
    def save(self,result,**extra):
        data=asdict(result);data["output_path"]=str(result.output_path) if result.output_path else None;self.save_state(result.work_unit_id,result.status,data,**extra)
    def save_state(self,unit_id,status,payload=None,**extra):
        path=self.path(unit_id);path.parent.mkdir(parents=True,exist_ok=True);data=dict(payload or {});data.update(extra);data.update(work_unit_id=unit_id,status=status,job_signature=self.signature,updated_at=datetime.now(timezone.utc).isoformat());_atomic_json(path,data)
    def mark_pending(self,unit):self.save_state(unit.work_unit_id,"Pending",{"work_unit":_unit_payload(unit)})
    def mark_starting(self,unit,attempt):self.save_state(unit.work_unit_id,"Starting",{"work_unit":_unit_payload(unit),"attempt_count":attempt})
    def mark_running(self,unit,attempt,pid=None):self.save_state(unit.work_unit_id,"Running",{"work_unit":_unit_payload(unit),"attempt_count":attempt,"pid":pid,"started_at":datetime.now(timezone.utc).isoformat()})
    def load(self,unit_id):
        path=self.path(unit_id)
        try:return json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError):return None
    def load_valid(self,unit_id):
        d=self.load(unit_id)
        if not d:return None
        out=Path(d["output_path"]) if d.get("output_path") else None
        if d.get("job_signature")!=self.signature or d.get("status")!="Complete" or out is None or not out.is_file() or _checksum(out)!=d.get("checksum"):return None
        return WorkUnitResult(unit_id,"Complete",out,int(d.get("attempt_count",1)),float(d.get("runtime_seconds",0)),checksum=d["checksum"],metrics=d.get("metrics",{}))
    def reconcile(self,unit_id,*,pid_alive=lambda _pid:False,result_path=None):
        remove_invalid_temporaries(self.path(unit_id).parent)
        data=self.load(unit_id)
        if not data or data.get("job_signature")!=self.signature:return None
        status=data.get("status")
        if status=="Starting" and not data.get("pid"):self.save_state(unit_id,"Interrupted",data,error_code="INTERRUPTED_BEFORE_LAUNCH",message="Processing stopped before the worker launched.");return "Interrupted"
        if status=="Running" and result_path and Path(result_path).is_file():
            try:
                raw=json.loads(Path(result_path).read_text(encoding="utf-8"));success=raw.get("status")=="success"
                result=WorkUnitResult(unit_id,"Complete" if success else "Failed",error_code=str(raw.get("error_code") or "EXECUTION_FAILED"),message="; ".join(raw.get("errors",())) or "Recovered completed PBM worker result.")
                self.save(result,reconciled_from=str(result_path));return result.status
            except (OSError,ValueError,TypeError):pass
        if status=="Running" and not pid_alive(data.get("pid")):self.save_state(unit_id,"Interrupted",data,error_code="INTERRUPTED_WORKER",message="The recorded worker is no longer running and wrote no terminal result.");return "Interrupted"
        return status

class PolygonProductWorkScheduler:
    def __init__(self,units,executor,checkpoint_store,concurrency=1,retry_count=2,transient=lambda e:False,progress_callback=None,circuit_breaker=None):
        self.units=tuple(units);self.executor=executor;self.store=checkpoint_store;self.concurrency=max(1,min(int(concurrency),4));self.retry_count=max(0,retry_count);self.transient=transient;self.callback=progress_callback;self.breaker=circuit_breaker or WorkFailureCircuitBreaker();self._pause=threading.Event();self._cancel=threading.Event();self.stop_reason=""
    def pause(self):self._pause.set()
    def resume(self):self._pause.clear()
    def cancel(self):self._cancel.set()
    def run(self):
        started=time.monotonic();results={};pending=[];active={};retries=0
        for unit in self.units:
            cached=self.store.load_valid(unit.work_unit_id)
            if cached:results[unit.work_unit_id]=cached
            else:self.store.mark_pending(unit);pending.append(unit)
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            while pending or active:
                while pending and len(active)<self.concurrency and not self._pause.is_set() and not self._cancel.is_set() and not self.stop_reason:
                    unit=pending.pop(0);self.store.mark_starting(unit,1);active[pool.submit(self._execute,unit,1)]=(unit,1);self.store.mark_running(unit,1)
                self._emit(started,results,active,retries,len(pending))
                if self._cancel.is_set() or self.stop_reason:
                    for future in active:future.cancel()
                    if not active:break
                if not active:
                    if self._pause.is_set() or self.stop_reason:break
                    time.sleep(.01);continue
                done,_=wait(active,timeout=.05,return_when=FIRST_COMPLETED)
                for future in done:
                    unit,attempt=active.pop(future)
                    try:result=future.result()
                    except Exception as exc:
                        code=_exception_code(exc)
                        if self.transient(exc) and code not in DETERMINISTIC_CODES|{NATIVE_CRASH_CODE} and attempt<=self.retry_count:
                            retries+=1;self.store.mark_starting(unit,attempt+1);active[pool.submit(self._execute,unit,attempt+1)]=(unit,attempt+1);self.store.mark_running(unit,attempt+1);continue
                        result=WorkUnitResult(unit.work_unit_id,"Failed",attempt_count=attempt,error_code=code,message=str(exc))
                    results[unit.work_unit_id]=result;self.store.save(result)
                    if result.status=="Failed":
                        decision=self.breaker.record(result)
                        if decision.stop or decision.pause:self.stop_reason=decision.reason;self._pause.set()
        for unit in pending:
            if not self.store.load(unit.work_unit_id):self.store.mark_pending(unit)
        self._emit(started,results,{},retries,len(pending),terminal=True)
        fallback="Pending" if self.stop_reason or self._pause.is_set() else "Cancelled"
        return tuple(results.get(unit.work_unit_id,WorkUnitResult(unit.work_unit_id,fallback,message=self.stop_reason or "Cancelled before execution.")) for unit in self.units)
    def _execute(self,unit,attempt):
        start=time.monotonic();result=self.executor(unit,attempt)
        if result.status=="Complete" and result.output_path:
            result=replace(result,attempt_count=attempt,runtime_seconds=time.monotonic()-start,checksum=_checksum(result.output_path))
        return result
    def _emit(self,started,results,active,retries,pending,terminal=False):
        if not self.callback:return
        completed=sum(x.status=="Complete" for x in results.values());failed=sum(x.status=="Failed" for x in results.values());elapsed=time.monotonic()-started;attempted=completed+failed+len(active);rate=completed/elapsed if elapsed else 0;eta=pending/rate if completed>=2 and rate>0 else None
        stage="Needs Technical Review" if self.stop_reason else ("Paused" if self._pause.is_set() else ("Finalizing" if terminal else "Processing Work Units"))
        self.callback(SchedulerProgress(stage,completed,len(self.units),failed,len(active),retries,elapsed,tuple(v[0].work_unit_id for v in active.values()),next(reversed(results),"") if results else "",eta,attempted,max(0,len(self.units)-completed-failed-len(active)),bool(self._pause.is_set()),self.stop_reason))

def _atomic_json(path,data):atomic_write_json(path,data)
def _checksum(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def _exception_code(exc):
    explicit=getattr(exc,"code","")
    if explicit:return str(getattr(explicit,"value",explicit))
    text=str(exc).lower()
    if "collinear" in text:return "HAG_COLLINEAR_INPUT"
    if "empty point" in text or "no point" in text:return "EMPTY_SPATIAL_READ"
    if "native" in text and "crash" in text:return NATIVE_CRASH_CODE
    return "EXECUTION_FAILED"
def _error_signature(result):
    normalized=" ".join(result.message.lower().split())
    return hashlib.sha256(f"{result.error_code}:{normalized}".encode()).hexdigest()[:16]
def _unit_index(unit_id):
    try:return int(unit_id.rsplit("-",1)[-1])
    except ValueError:return -1
def _adjacent_tail(records):
    if not records:return 0
    count=1
    for previous,current in zip(reversed(records[:-1]),reversed(records[1:])):
        if previous[2]>=0 and current[2]-previous[2]==1:count+=1
        else:break
    return count
def _unit_payload(unit):
    return {"work_unit_id":unit.work_unit_id,"execution_order":unit.execution_order,"source_paths":[str(x) for x in unit.source_paths],"core_extent":asdict(unit.core_extent),"read_extent":asdict(unit.read_extent)}
