"""Checkpointed bounded-concurrency scheduler for polygon work units."""
from __future__ import annotations
import hashlib,json,threading,time
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from pathlib import Path
from typing import Callable
from .source_aware_processing import WorkUnit

@dataclass(frozen=True)
class WorkUnitResult:
 work_unit_id: str; status: str; output_path: Path|None=None; attempt_count: int=1; runtime_seconds: float=0; error_code: str=''; message: str=''; checksum: str=''; metrics: dict=field(default_factory=dict)

@dataclass(frozen=True)
class SchedulerProgress:
 stage: str; completed: int; total: int; failed: int; active: int; retries: int; elapsed_seconds: float; current_units: tuple[str,...]; latest_completed: str=''; eta_seconds: float|None=None

class CheckpointStore:
 def __init__(self,folder,job_signature):self.folder=Path(folder);self.signature=job_signature;self.folder.mkdir(parents=True,exist_ok=True)
 def path(self,unit_id):return self.folder/unit_id/'status.json'
 def save(self,result):
  path=self.path(result.work_unit_id);path.parent.mkdir(parents=True,exist_ok=True);data=asdict(result);data['output_path']=str(result.output_path) if result.output_path else None;data['job_signature']=self.signature;data['updated_at']=datetime.now(timezone.utc).isoformat();tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8');tmp.replace(path)
 def load_valid(self,unit_id):
  path=self.path(unit_id)
  if not path.exists():return None
  try:d=json.loads(path.read_text(encoding='utf-8'))
  except (OSError,ValueError):return None
  out=Path(d['output_path']) if d.get('output_path') else None
  if d.get('job_signature')!=self.signature or d.get('status')!='Complete' or out is None or not out.is_file() or _checksum(out)!=d.get('checksum'):return None
  return WorkUnitResult(unit_id,'Complete',out,int(d.get('attempt_count',1)),float(d.get('runtime_seconds',0)),checksum=d['checksum'],metrics=d.get('metrics',{}))

class PolygonProductWorkScheduler:
 def __init__(self,units,executor,checkpoint_store,concurrency=1,retry_count=2,transient=lambda e:False,progress_callback=None):
  self.units=tuple(units);self.executor=executor;self.store=checkpoint_store;self.concurrency=max(1,min(int(concurrency),4));self.retry_count=max(0,retry_count);self.transient=transient;self.callback=progress_callback;self._pause=threading.Event();self._cancel=threading.Event()
 def pause(self):self._pause.set()
 def resume(self):self._pause.clear()
 def cancel(self):self._cancel.set()
 def run(self):
  started=time.monotonic();results={};pending=[]
  for u in self.units:
   cached=self.store.load_valid(u.work_unit_id)
   if cached:results[u.work_unit_id]=cached
   else:pending.append(u)
  active={};retries=0
  with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
   while pending or active:
    while pending and len(active)<self.concurrency and not self._pause.is_set() and not self._cancel.is_set():
     u=pending.pop(0);active[pool.submit(self._execute,u,1)]=(u,1)
    self._emit(started,results,active,retries)
    if self._cancel.is_set():
     for future in active:future.cancel()
     break
    if not active:time.sleep(.01);continue
    done,_=wait(active,timeout=.05,return_when=FIRST_COMPLETED)
    for f in done:
     u,attempt=active.pop(f)
     try:res=f.result()
     except Exception as exc:
      if self.transient(exc) and attempt<=self.retry_count:retries+=1;active[pool.submit(self._execute,u,attempt+1)]=(u,attempt+1);continue
      res=WorkUnitResult(u.work_unit_id,'Failed',attempt_count=attempt,error_code=getattr(exc,'code','EXECUTION_FAILED'),message=str(exc))
     results[u.work_unit_id]=res;self.store.save(res)
  self._emit(started,results,{},retries,terminal=True)
  return tuple(results.get(u.work_unit_id,WorkUnitResult(u.work_unit_id,'Cancelled',message='Cancelled before execution.')) for u in self.units)
 def _execute(self,u,attempt):
  start=time.monotonic();res=self.executor(u,attempt)
  if res.status=='Complete' and res.output_path:
   checksum=_checksum(res.output_path);res=WorkUnitResult(res.work_unit_id,res.status,res.output_path,attempt,time.monotonic()-start,res.error_code,res.message,checksum,res.metrics)
  return res
 def _emit(self,started,results,active,retries,terminal=False):
  if not self.callback:return
  completed=sum(x.status=='Complete' for x in results.values());failed=sum(x.status=='Failed' for x in results.values());elapsed=time.monotonic()-started;rate=completed/elapsed if elapsed>0 else 0;remaining=len(self.units)-completed-failed;eta=remaining/rate if completed>=2 and rate>0 else None
  self.callback(SchedulerProgress('Finalizing' if terminal else 'Processing Work Units',completed,len(self.units),failed,len(active),retries,elapsed,tuple(v[0].work_unit_id for v in active.values()),next(reversed(results),'') if results else '',eta))

def _checksum(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
