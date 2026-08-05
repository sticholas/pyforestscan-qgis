"""Project-scoped processing state and legacy-state migration."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any

STATE_SCHEMA_VERSION=2
def project_identity(project_path: str="", session_uuid: str="") -> str:
    return f"file:{project_path.casefold()}" if project_path else f"unsaved:{session_uuid or uuid.uuid4()}"

@dataclass
class ProjectProcessingState:
    repository_path: str=""
    repository_kind: str=""
    polygon_label: str=""
    polygon_feature_ids: tuple[str,...]=()
    polygon_area: float|None=None
    polygon_geometry_hash: str=""
    selected_products: tuple[str,...]=()
    output_override: str=""
    prerun_valid: bool=False
    current_job: Any=None
    current_outputs: tuple[str,...]=()
    previous_runs: tuple[Any,...]=()
    status: str="Needs setup"

    def repository_changed(self,path: str,kind: str):
        self.repository_path,self.repository_kind=path,kind; self.polygon_label=""; self.polygon_feature_ids=(); self.polygon_area=None; self.polygon_geometry_hash=""; self.prerun_valid=False; self.current_job=None; self.current_outputs=(); self.status="Needs area" if path else "Needs setup"
    def polygon_changed(self,label: str,ids,area: float|None,geometry_hash: str):
        self.polygon_label=label; self.polygon_feature_ids=tuple(map(str,ids)); self.polygon_area=area; self.polygon_geometry_hash=geometry_hash; self.prerun_valid=False; self.current_job=None; self.current_outputs=(); self.status="Needs Prerun Check"
    def reset_transient(self):
        previous=self.previous_runs; self.__dict__.update(ProjectProcessingState(previous_runs=previous).__dict__)

class ProjectSessionStore:
    def __init__(self): self._states={}
    def state_for(self,identity: str): return self._states.setdefault(identity,ProjectProcessingState())

def footer_status(backend: str,state: ProjectProcessingState) -> tuple[str,str,str,str]:
    lidar=f"{state.repository_kind.upper()} selected" if state.repository_path else "Not selected"
    area=f"{state.polygon_area/10000:.3g} ha" if state.polygon_area is not None else ("Full folder" if state.repository_path and state.repository_kind!="ept" else "Not selected")
    return (backend,lidar,area,state.status)

def migrate_legacy_settings(settings) -> bool:
    version=int(settings.value("state/schema_version",0) or 0)
    if version>=STATE_SCHEMA_VERSION:return False
    for key in ("current_dataset","latest_dataset","planning_status","current_job"):
        settings.remove(key)
    settings.setValue("state/schema_version",STATE_SCHEMA_VERSION); return True
