"""One-current-job identity and stale callback isolation."""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
from datetime import datetime,timezone
import uuid

TERMINAL_STATES={'complete','failed','cancelled','scientific_blocker'}

@dataclass(frozen=True)
class CurrentJobToken:
    project_id:str;session_id:str;logical_job_id:str;attempt_id:str;plan_signature:str;repository_identity:str;polygon_identity:str;created_at:str
    @classmethod
    def create(cls,project_id,session_id,plan_signature='',repository_identity='',polygon_identity=''):
        return cls(str(project_id),str(session_id),uuid.uuid4().hex,uuid.uuid4().hex,str(plan_signature),str(repository_identity),str(polygon_identity),datetime.now(timezone.utc).isoformat())
    def to_dict(self):return asdict(self)

@dataclass(frozen=True)
class ActiveJobRecord:
    token:CurrentJobToken;state:str='preparing';final_output_paths:tuple[str,...]=()

class ActiveProcessingJobController:
    def __init__(self):self._current=None;self._history=[]
    @property
    def current(self):return self._current
    @property
    def history(self):return tuple(self._history)
    @property
    def is_running(self):return bool(self._current and self._current.state not in TERMINAL_STATES)
    def begin(self,token):
        if self.is_running:raise RuntimeError('Processing is already running.')
        if self._current is not None:self._history.insert(0,self._current)
        self._current=ActiveJobRecord(token,'preparing',());return self._current
    def accepts(self,token):return bool(self._current and token==self._current.token)
    def update(self,token,state,final_output_paths=()):
        if not self.accepts(token):return False
        self._current=replace(self._current,state=str(state),final_output_paths=tuple(str(path) for path in final_output_paths));return True
    def make_current_and_continue(self,logical_job_id):
        if self.is_running:raise RuntimeError('Processing is already running.')
        for index,record in enumerate(self._history):
            if record.token.logical_job_id==logical_job_id:
                if self._current is not None:self._history.insert(0,self._current)
                self._current=self._history.pop(index+1 if self._current is not None else index);return self._current
        raise KeyError(logical_job_id)
    def clear_current(self):
        if self._current is not None:self._history.insert(0,self._current)
        self._current=None

    def current_output_paths(self,token,paths):
        if not self.accepts(token) or self._current.state!='complete':return ()
        allowed=set(self._current.final_output_paths);return tuple(str(path) for path in paths if str(path) in allowed)
