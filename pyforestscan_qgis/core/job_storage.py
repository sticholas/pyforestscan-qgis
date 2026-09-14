"""Non-destructive classification and maintenance for durable job storage."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import time
class RetentionCategory(str,Enum):REQUIRED="REQUIRED";RECOVERABLE="RECOVERABLE";DIAGNOSTIC="DIAGNOSTIC";TEMPORARY="TEMPORARY";CACHE="CACHE"
@dataclass(frozen=True)
class MaintenanceCandidate:path:Path;category:RetentionCategory;reason:str
def classify_job_path(path):
 path=Path(path);name=path.name.lower();parts={x.lower() for x in path.parts}
 if name.endswith((".tif",".tiff",".csv")) or name in {"generated_outputs.json","terminal_result.json"}:return RetentionCategory.REQUIRED
 if "work_units" in parts or name in {"coordinator_state.json","coordinator_payload.pkl"}:return RetentionCategory.RECOVERABLE
 if "diagnostics" in parts or name.endswith((".log",".traceback.txt")):return RetentionCategory.DIAGNOSTIC
 if name.endswith(".tmp") or name in {"heartbeat.json","coordinator.lock"}:return RetentionCategory.TEMPORARY
 return RetentionCategory.CACHE
def maintenance_candidates(root,*,older_than_seconds=7*24*3600,now=None):
 root=Path(root);current=time.time() if now is None else float(now);selected=[]
 if not root.exists():return ()
 for path in root.rglob("*"):
  if not path.is_file():continue
  category=classify_job_path(path)
  if category not in {RetentionCategory.TEMPORARY,RetentionCategory.CACHE}:continue
  try:age=current-path.stat().st_mtime
  except OSError:continue
  if age>=older_than_seconds:selected.append(MaintenanceCandidate(path,category,f"stale for {age:.0f} seconds"))
 return tuple(selected)
def clean_maintenance_candidates(candidates,*,dry_run=True):
 removed=[]
 for item in candidates:
  if item.category not in {RetentionCategory.TEMPORARY,RetentionCategory.CACHE}:continue
  if not dry_run:
   try:item.path.unlink()
   except FileNotFoundError:pass
  removed.append(item.path)
 return tuple(removed)
