"""Own one source-aware polygon CHM job outside QGIS."""
from __future__ import annotations
import argparse,os,pickle,time,traceback,json
from pathlib import Path
from pyforestscan_qgis.backend_runner.job_coordinator import DurableJobCoordinator,ProcessingProgressSnapshot,aggregate_work_unit_statuses,utc_now
from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.backend_runner.runtime_contract import inspect_runtime_contract
from pyforestscan_qgis.core.backend.processing_engine import ProcessingRuntimeToken,contract_hash,product_capability_hash

def _atomic_pickle(path,value):
    import uuid
    temporary=path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("wb") as stream:
        pickle.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)

def run_payload(payload_path):
    with Path(payload_path).open("rb") as stream:payload=pickle.load(stream)
    job_dir=Path(payload["job_dir"]);job_id=payload["job_id"];attempt_id=payload["attempt_id"];coordinator=DurableJobCoordinator(job_dir);coordinator.recover();coordinator.write_identity(job_id,attempt_id,os.sys.argv);started=time.monotonic()
    products=tuple(product.value for product in payload["report"].request.products)
    _validate_and_trace_runtime(job_dir,job_id,products)
    def progress(item):
        stage=getattr(item,"status","Processing");message=getattr(item,"message","");plan=payload["plan"];counts=aggregate_work_unit_statuses(payload["context"].run_folder/"work_units",plan.candidate_count,plan.required_count)
        coordinator.write_snapshot(ProcessingProgressSnapshot(job_id,attempt_id,"running",plan.candidate_count,completed=counts["completed"]+counts["complete_nodata"],failed=counts["failed"],pending=counts["pending"],running=counts["running"],attempted=counts["attempted"],current_stage=str(stage),current_activity=str(message),elapsed_seconds=time.monotonic()-started,last_heartbeat=utc_now(),candidate_work_units=plan.candidate_count,required_work_units=plan.required_count,skipped_outside_polygon=counts["skipped_outside_polygon"],complete_nodata=counts["complete_nodata"]))
    try:
        os.environ["PYFORESTSCAN_POLYGON_COORDINATOR"]="1"
        from pyforestscan_qgis.core.polygon_batch import _execute_source_aware_chm
        adapter=PyForestScanAdapter(execution_mode="qgis_python")
        result=_execute_source_aware_chm(payload["report"],adapter,Path(payload["batch_folder"]),payload["context"],payload["source"],payload["plan"],item_callback=progress)
        failed=any(getattr(item,"status","").lower()!="completed" for item in result.items)
        result_path=job_dir/"coordinator_result.pkl";_atomic_pickle(result_path,result)
        state="scientific_blocker" if failed else "complete"
        atomic_write_json(job_dir/"terminal_result.json",{"job_id":job_id,"attempt_id":attempt_id,"state":state,"result_path":str(result_path),"error":"One or more required work areas failed." if failed else "","finished_at":utc_now()})
        plan=payload["plan"];counts=aggregate_work_unit_statuses(payload["context"].run_folder/"work_units",plan.candidate_count,plan.required_count)
        coordinator.write_snapshot(ProcessingProgressSnapshot(job_id,attempt_id,state,plan.candidate_count,completed=counts["completed"]+counts["complete_nodata"],failed=counts["failed"],pending=counts["pending"],running=counts["running"],attempted=counts["attempted"],current_stage="Scientific Blocker" if failed else "Complete",current_activity="Completed work was preserved." if failed else "",circuit_breaker_state="open" if failed else "closed",finalization_state="blocked" if failed else "complete",elapsed_seconds=time.monotonic()-started,last_heartbeat=utc_now(),candidate_work_units=plan.candidate_count,required_work_units=plan.required_count,skipped_outside_polygon=counts["skipped_outside_polygon"],complete_nodata=counts["complete_nodata"],stop_reason="One or more required work areas failed." if failed else ""))
        return 1 if failed else 0
    except Exception as exc:
        atomic_write_json(job_dir/"terminal_result.json",{"job_id":job_id,"attempt_id":attempt_id,"state":"failed","error":str(exc),"traceback":traceback.format_exc(),"finished_at":utc_now()})
        coordinator.write_snapshot(ProcessingProgressSnapshot(job_id,attempt_id,"scientific_blocker",len(payload["plan"].work_units),current_stage="Scientific Blocker",current_activity=str(exc),finalization_state="blocked",elapsed_seconds=time.monotonic()-started,last_heartbeat=utc_now()))
        return 1

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--payload",type=Path,required=True);args=parser.parse_args();return run_payload(args.payload)
def _validate_and_trace_runtime(job_dir,job_id,products):
    contract=inspect_runtime_contract();token=ProcessingRuntimeToken.from_dict(json.loads(os.environ.get("PYFORESTSCAN_RUNTIME_TOKEN","{}")))
    if token is None:raise RuntimeError("ENGINE_RUNTIME_TOKEN_MISSING: polygon coordinator was not launched by the Processing Engine.")
    identity_matches=(
        str(Path(token.executable).resolve())==str(Path(contract.get("python_executable","")).resolve())
        and token.contract_hash==contract_hash(contract)
        and token.backend_runner_hash==str(contract.get("runner_sha256",""))
        and token.plugin_build_id==str(contract.get("plugin_build_id",""))
        and token.dependency_manifest_hash==str(contract.get("dependency_manifest_hash",""))
        and token.product_capability_hash==product_capability_hash(tuple(products))
    )
    if not identity_matches:raise RuntimeError("ENGINE_RUNTIME_CHANGED: polygon coordinator runtime differs from the verified Processing Engine.")
    path=Path(job_dir)/"execution_runtime_trace.json"
    try:trace=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"stages":{}}
    except (OSError,ValueError):trace={"stages":{}}
    trace.setdefault("stages",{})["polygon_coordinator"]={"job_id":job_id,"pid":os.getpid(),"parent_pid":os.getppid(),"executable":contract.get("python_executable"),"sys_prefix":os.sys.prefix,"cwd":os.getcwd(),"pythonpath":os.environ.get("PYTHONPATH",""),"path":os.environ.get("PATH",""),"sys_path":contract.get("sys_path",[]),"module_locations":contract.get("module_locations",{}),"protocol":contract.get("protocol_version"),"contract_hash":contract_hash(contract)}
    atomic_write_json(path,trace)

if __name__=="__main__":raise SystemExit(main())
