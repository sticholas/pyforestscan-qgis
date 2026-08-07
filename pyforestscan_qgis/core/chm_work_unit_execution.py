"""Shared CHM work-unit validation and diagnostic contract."""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from .atomic_state import atomic_write_json

def validate_existing_hag_array(point_array,request):
    names=set(getattr(point_array.dtype,"names",()) or ())
    dimension=getattr(request,"hag_source_dimension","HeightAboveGround")
    if dimension not in names:raise RuntimeError(f"HAG_METHOD_MISMATCH: planned existing normalized height dimension {dimension} is missing.")
    values=point_array[dimension]
    finite=[float(value) for value in values if _finite(value)]
    ordered=sorted(finite);nonzero=sum(abs(value)>1e-9 for value in finite)
    statistics={"dimension":dimension,"value_count":len(values),"finite_count":len(finite),"nonfinite_count":len(values)-len(finite),"nonzero_count":nonzero,"minimum":min(finite) if finite else None,"maximum":max(finite) if finite else None,"percentiles":{str(p):_percentile(ordered,p) for p in (1,5,25,50,75,95,99)},"unit_assumption":"source horizontal/vertical linear unit","planned_method":getattr(request,"hag_method",""),"method_signature":getattr(request,"hag_method_signature","")}
    if not finite or not nonzero or statistics["maximum"]-statistics["minimum"]<=1e-9:raise RuntimeError("INVALID_EXISTING_HAG: HeightAboveGround values are absent, nonfinite, zero, or constant.")
    diagnostics_value=getattr(request,"diagnostics_path",None)
    if diagnostics_value:
        diagnostics=Path(diagnostics_value);diagnostics.mkdir(parents=True,exist_ok=True)
        atomic_write_json(diagnostics/"source_schema.json",{"dimensions":sorted(names),"height_dimension":dimension})
        atomic_write_json(diagnostics/"bounded_read_result.json",{"point_count":len(values),"finite_hag_count":len(finite),"status":"read_complete"})
        atomic_write_json(diagnostics/"point_statistics.json",statistics)
        atomic_write_json(diagnostics/"hag_execution_decision.json",{"planned_method":statistics["planned_method"],"executed_method":"existing_normalized_height","source_dimension":dimension,"method_signature":statistics["method_signature"],"status":"accepted"})
    return statistics

def write_work_unit_diagnostic(path,name,payload):
    if not path:return None
    root=Path(path);root.mkdir(parents=True,exist_ok=True);return atomic_write_json(root/name,_json_value(payload))

def _json_value(value):
    if isinstance(value,Path):return str(value)
    if isinstance(value,Enum):return value.value
    if is_dataclass(value):return _json_value(asdict(value))
    if isinstance(value,dict):return {str(key):_json_value(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [_json_value(item) for item in value]
    return value

def _finite(value):
    import math
    try:return math.isfinite(float(value))
    except (TypeError,ValueError):return False
def _percentile(values,p):
    if not values:return None
    index=(len(values)-1)*p/100.0;low=int(index);high=min(len(values)-1,low+1);fraction=index-low
    return values[low]*(1-fraction)+values[high]*fraction
