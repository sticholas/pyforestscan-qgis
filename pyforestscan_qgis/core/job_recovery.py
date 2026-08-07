"""Geometry-driven reconciliation of durable polygon work-unit state."""
from dataclasses import dataclass
import hashlib,json
from pathlib import Path
from .atomic_state import atomic_write_json

@dataclass(frozen=True)
class RecoverySummary:
    recovered_complete:int;reclassified_outside:int;pending_required:int;failed_required:int;message:str

def reconcile_polygon_job(work_units_folder,plan,job_signature,expected_hag_method_signature=""):
    folder=Path(work_units_folder);complete=outside=pending=failed=0
    for unit in plan.candidate_work_units or plan.work_units:
        path=folder/unit.work_unit_id/"status.json"
        if not unit.required_for_output:
            atomic_write_json(path,{"work_unit_id":unit.work_unit_id,"status":"SkippedOutsidePolygon","job_signature":job_signature,"reason_code":"OUTSIDE_EXACT_POLYGON","polygon_intersection_area":unit.polygon_intersection_area,"polygon_coverage_percent":unit.polygon_coverage_percent,"buffered_polygon_intersects":unit.buffered_polygon_intersects,"source_coverage_expectation":unit.source_coverage_expectation,"output_required":False});outside+=1;continue
        data=_read(path)
        if not data:pending+=1;continue
        if data.get("status") in {"Complete","CompleteNoData"} and _compatible(data,unit,plan,expected_hag_method_signature):
            data.update(job_signature=job_signature,grid_signature=plan.grid.grid_signature,source_plan_signature=plan.plan_signature,status=data.get("status"))
            if data.get("status")=="Complete" and data.get("output_path"):data["checksum"]=_checksum(Path(data["output_path"]))
            atomic_write_json(path,data);complete+=1;continue
        if data.get("status") in {"Pending","Starting","Running","Interrupted","Cancelled"}:pending+=1
        elif data.get("status")=="Failed":failed+=1
        else:pending+=1
    return RecoverySummary(complete,outside,pending,failed,f"{complete} completed processing areas were recovered. Areas outside the selected polygon were excluded, and processing can continue for the remaining required areas.")

def _read(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return None

def _compatible(data,unit,plan,expected_hag_method_signature):
    if data.get("status")=="CompleteNoData":return True
    output=Path(data.get("output_path") or "")
    if not output.is_file():return False
    checksum=data.get("checksum")
    if checksum and _checksum(output)!=checksum:return False
    metrics=data.get("metrics") or {};recorded_hag=metrics.get("hag_method_signature") or data.get("hag_method_signature")
    if expected_hag_method_signature and recorded_hag and recorded_hag!=expected_hag_method_signature:return False
    recorded_grid=metrics.get("grid_signature") or data.get("grid_signature")
    if recorded_grid and recorded_grid!=plan.grid.grid_signature:return False
    core=(metrics.get("core_extent") or (data.get("work_unit") or {}).get("core_extent"))
    if core and any(abs(float(core.get(key))-float(getattr(unit.core_extent,key)))>1e-7 for key in ("xmin","ymin","xmax","ymax")):return False
    return True

def _checksum(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()
