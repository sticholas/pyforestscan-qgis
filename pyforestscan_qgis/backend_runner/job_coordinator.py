"""Durable per-job PBM coordinator independent of QGIS and Qt."""
from __future__ import annotations
import argparse,json,os,subprocess,time,uuid
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path
from pyforestscan_qgis.core.atomic_state import atomic_write_json,remove_invalid_temporaries
from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs

def utc_now():return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class ProcessingProgressSnapshot:
    job_id:str;attempt_id:str;state:str;total_work_units:int;completed:int=0;failed:int=0;pending:int=0;running:int=0;attempted:int=0;current_work_unit_id:str="";current_stage:str="Preparing";current_activity:str="";elapsed_seconds:float=0.;last_heartbeat:str="";pilot_state:str="pending";circuit_breaker_state:str="closed";finalization_state:str="pending";source_count:int=1;candidate_work_units:int=0;required_work_units:int=0;skipped_outside_polygon:int=0;complete_nodata:int=0;stop_reason:str="";current_work_unit_ids:tuple[str,...]=();progress_percent:int=0;eta_seconds:float|None=None;eta_confidence:str="CALCULATING";health:str="WORKING";target_concurrency:int=1;worker_details:tuple[dict,...]=();points_processed:int=0

def aggregate_work_unit_statuses(folder,candidate_work_units,required_work_units):
    counts={"completed":0,"complete_nodata":0,"failed":0,"pending":0,"running":0,"attempted":0,"skipped_outside_polygon":0,"current_work_unit_ids":[]}
    for path in Path(folder).glob("wu-*/status.json"):
        try:data=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError):continue
        status=data.get("status","")
        if status=="Complete":counts["completed"]+=1
        elif status=="CompleteNoData":counts["complete_nodata"]+=1
        elif status=="SkippedOutsidePolygon":counts["skipped_outside_polygon"]+=1
        elif status=="Failed":counts["failed"]+=1
        elif status in {"Starting","Running"}:counts["running"]+=1;counts["current_work_unit_ids"].append(str(data.get("work_unit_id") or path.parent.name))
        elif status=="Pending":counts["pending"]+=1
    counts["attempted"]=counts["completed"]+counts["complete_nodata"]+counts["failed"]+counts["running"]
    counts["candidate_work_units"]=candidate_work_units;counts["required_work_units"]=required_work_units;counts["source_count"]=1
    return counts

class DurableJobCoordinator:
    def __init__(self,job_dir):
        self.job_dir=Path(job_dir);self.commands=self.job_dir/"commands";self.acks=self.job_dir/"command_acknowledgements";self.commands.mkdir(parents=True,exist_ok=True);self.acks.mkdir(parents=True,exist_ok=True)
    def write_identity(self,job_id,attempt_id,command):
        atomic_write_json(self.job_dir/"coordinator_identity.json",{"job_id":job_id,"attempt_id":attempt_id,"pid":os.getpid(),"executable":str(Path(os.sys.executable)),"command":list(command),"started_at":utc_now()})
    def write_snapshot(self,snapshot):
        payload=asdict(snapshot);payload["last_heartbeat"]=utc_now();atomic_write_json(self.job_dir/"progress_snapshot.json",payload);atomic_write_json(self.job_dir/"heartbeat.json",{"job_id":snapshot.job_id,"attempt_id":snapshot.attempt_id,"pid":os.getpid(),"timestamp":payload["last_heartbeat"],"state":snapshot.state})
    def write_terminal_snapshot(self,snapshot):
        """Publish terminal progress and close the heartbeat lifecycle."""
        payload=asdict(snapshot);stopped=utc_now();payload["last_heartbeat"]=stopped
        atomic_write_json(self.job_dir/"progress_snapshot.json",payload)
        atomic_write_json(self.job_dir/"heartbeat.json",{"job_id":snapshot.job_id,"attempt_id":snapshot.attempt_id,"pid":os.getpid(),"timestamp":stopped,"stopped_at":stopped,"state":snapshot.state,"active":False})
    def command(self,job_id,attempt_id,name,expected_state,requester="qgis"):
        command_id=str(uuid.uuid4());payload={"job_id":job_id,"attempt_id":attempt_id,"command_id":command_id,"command":name,"timestamp":utc_now(),"requester":requester,"expected_current_state":expected_state};atomic_write_json(self.commands/f"{command_id}.json",payload);return command_id
    def acknowledge_commands(self,job_id,attempt_id,state):
        for path in sorted(self.commands.glob("*.json")):
            try:data=json.loads(path.read_text(encoding="utf-8"))
            except (OSError,ValueError):continue
            if data.get("job_id")!=job_id or data.get("attempt_id")!=attempt_id:continue
            accepted=data.get("expected_current_state") in {"",state}
            atomic_write_json(self.acks/path.name,{**data,"acknowledged_at":utc_now(),"accepted":accepted,"coordinator_state":state});path.unlink(missing_ok=True)
    def recover(self):
        return remove_invalid_temporaries(self.job_dir)

def parse_args():
    p=argparse.ArgumentParser();p.add_argument("--job-dir",type=Path,required=True);p.add_argument("--job-id",required=True);p.add_argument("--attempt-id",required=True);p.add_argument("--work-unit-spec",type=Path,action="append",default=[]);return p.parse_args()
def main():
    args=parse_args();coordinator=DurableJobCoordinator(args.job_dir);coordinator.recover();coordinator.write_identity(args.job_id,args.attempt_id,os.sys.argv);started=time.monotonic();total=len(args.work_unit_spec);completed=failed=0
    coordinator.write_snapshot(ProcessingProgressSnapshot(args.job_id,args.attempt_id,"running",total,pending=total,last_heartbeat=utc_now()))
    results=[]
    for index,spec in enumerate(args.work_unit_spec):
        coordinator.acknowledge_commands(args.job_id,args.attempt_id,"running")
        snapshot=ProcessingProgressSnapshot(args.job_id,args.attempt_id,"running",total,completed,failed,total-index-1,1,index,str(index+1),"Generating CHM",str(spec),time.monotonic()-started,utc_now(),"passed","closed","pending");coordinator.write_snapshot(snapshot)
        completed_process=subprocess.run([os.sys.executable,"-m","pyforestscan_qgis.backend_runner.run_processing_job","--spec",str(spec)],check=False,**hidden_subprocess_kwargs())
        result_path=spec.parent/"result.json";results.append({"spec":str(spec),"returncode":completed_process.returncode,"result":str(result_path)});completed+=completed_process.returncode==0;failed+=completed_process.returncode!=0
        coordinator.write_snapshot(ProcessingProgressSnapshot(args.job_id,args.attempt_id,"running",total,completed,failed,total-completed-failed,0,completed+failed,"", "Writing Area Result",str(result_path),time.monotonic()-started,utc_now(),"passed","closed","pending"))
    state="complete" if failed==0 else "scientific_blocker";terminal={"job_id":args.job_id,"attempt_id":args.attempt_id,"state":state,"completed":completed,"failed":failed,"results":results,"finished_at":utc_now()};atomic_write_json(args.job_dir/"terminal_result.json",terminal);coordinator.write_terminal_snapshot(ProcessingProgressSnapshot(args.job_id,args.attempt_id,state,total,completed,failed,0,0,total,"","Complete" if state=="complete" else "Scientific Blocker","",time.monotonic()-started,utc_now(),"passed","closed","complete" if state=="complete" else "blocked"));return 0 if state=="complete" else 1
if __name__=="__main__":raise SystemExit(main())
