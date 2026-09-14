"""Authoritative identity and validation for processing attempts."""
from __future__ import annotations
import hashlib, json, uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

@dataclass(frozen=True)
class ProcessingJobIdentity:
    job_id: str
    attempt_id: str
    project_identity: str
    session_id: str
    repository_identity: str
    repository_path_hash: str
    polygon_geometry_hash: str
    polygon_source_label: str
    polygon_feature_ids: tuple[str,...]
    plan_signature: str
    selected_products: tuple[str,...]
    output_root: str
    created_at: str

    @classmethod
    def create(cls, *, project_identity: str, session_id: str, repository_path: str, polygon_geometry_hash: str="", polygon_source_label: str="", polygon_feature_ids=(), plan_signature: str="", selected_products=(), output_root: str="", job_id: str|None=None):
        return cls(job_id or f"job-{uuid.uuid4().hex[:12]}", f"attempt-{uuid.uuid4().hex[:12]}", project_identity, session_id, hashlib.sha256(repository_path.casefold().encode()).hexdigest(), hashlib.sha256(repository_path.casefold().encode()).hexdigest(), polygon_geometry_hash, polygon_source_label, tuple(map(str,polygon_feature_ids)), plan_signature, tuple(selected_products), output_root, datetime.now(timezone.utc).isoformat())

    def new_attempt(self):
        data=asdict(self); data["attempt_id"]=f"attempt-{uuid.uuid4().hex[:12]}"; data["created_at"]=datetime.now(timezone.utc).isoformat(); return ProcessingJobIdentity(**data)

    def write_sidecar(self, output: Path) -> Path:
        target=Path(str(output)+".pyforestscan.json"); target.write_text(json.dumps(asdict(self),indent=2,sort_keys=True)+"\n",encoding="utf-8"); return target

def output_matches_attempt(path: Path, identity: ProcessingJobIdentity, backend_paths) -> bool:
    p=Path(path)
    if p not in {Path(x) for x in backend_paths} or not p.is_file(): return False
    side=Path(str(p)+".pyforestscan.json")
    if not side.exists(): return False
    try: data=json.loads(side.read_text(encoding="utf-8"))
    except (OSError,ValueError): return False
    return all(data.get(k)==getattr(identity,k) for k in ("job_id","attempt_id","project_identity","plan_signature","polygon_geometry_hash"))
