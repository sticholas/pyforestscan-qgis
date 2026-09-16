"""Live diagnostics for slow polygon prerun workers (PFS-REL-005C)."""
from __future__ import annotations
import json, sys, threading, time, traceback, uuid, inspect
from datetime import datetime, timezone
from pathlib import Path
from .atomic_state import atomic_write_json

class PrerunForensics:
    def __init__(self, root: Path | str):
        self.root=Path(root)/"prerun"/uuid.uuid4().hex
        self.root.mkdir(parents=True,exist_ok=True)
        self.live=self.root/"prerun_live_state.json"; self.ops=self.root/"prerun_operations.jsonl"
        self.started=time.monotonic(); self.thread_id=threading.get_ident(); self.thread_name=threading.current_thread().name
        self.stage="STARTING"; self.substage=""; self.last_operation=""; self.last_path=""; self._failure_payload={}; self._stop=threading.Event(); self._monitor=threading.Thread(target=self._watch,name="PyForestScan-Prerun-Diagnostics",daemon=True)
        self._write(); self._monitor.start()
    def set_stage(self, stage: str, substage: str = ""):
        self.stage=str(stage); self.substage=str(substage); self._write()
    def before_io(self, operation: str, path: str = ""):
        self.last_operation=str(operation); self.last_path=str(path); self._write()
        try:
            with self.ops.open("a",encoding="utf-8") as f: f.write(json.dumps({"event":"start","operation":operation,"path":path,"stage":self.stage,"substage":self.substage,"timestamp":datetime.now(timezone.utc).isoformat()})+"\n")
        except OSError: pass
    def after_io(self, operation: str, path: str = "", started: float | None = None):
        try:
            with self.ops.open("a",encoding="utf-8") as f: f.write(json.dumps({"event":"end","operation":operation,"path":path,"stage":self.stage,"duration_ms":None if started is None else (time.monotonic()-started)*1000,"timestamp":datetime.now(timezone.utc).isoformat()})+"\n")
        except OSError: pass
    def _state(self):
        state = {"schema":"pyforestscan-prerun-live-v1","attempt_id":self.root.name,"stage":self.stage,"substage":self.substage,"function":"","elapsed_ms":(time.monotonic()-self.started)*1000,"thread_id":self.thread_id,"thread_name":self.thread_name,"last_operation":self.last_operation,"last_path":self.last_path,"filesystem_calls":{},"network_calls":0,"catalog_queries":0,"header_reads":0,"point_reads":0,"updated_at":datetime.now(timezone.utc).isoformat()}
        state.update(self._failure_payload)
        return state
    def _write(self):
        try: atomic_write_json(self.live,self._state())
        except OSError: pass
    def _stack(self):
        frame=sys._current_frames().get(self.thread_id)
        if frame is None: return "worker frame unavailable\n"
        return f"Prerun worker\nThread: {self.thread_name} ({self.thread_id})\nStage: {self.stage}\nSubstage: {self.substage}\nElapsed: {(time.monotonic()-self.started):.3f}s\n\n"+"".join(traceback.format_stack(frame))
    def _watch(self):
        thresholds=(2,5,10); dumped=set()
        while not self._stop.wait(.25):
            self._write(); elapsed=time.monotonic()-self.started
            for threshold in thresholds:
                if elapsed>=threshold and threshold not in dumped:
                    dumped.add(threshold)
                    try: (self.root/f"prerun_stack_{threshold}s.txt").write_text(self._stack(),encoding="utf-8")
                    except OSError: pass
    def close(self, status="COMPLETED"):
        self.stage=status; self._stop.set(); self._write(); self._monitor.join(timeout=1)
        try: (self.root/"final_performance.json").write_text(json.dumps(self._state(),indent=2),encoding="utf-8")
        except OSError: pass
    def failure(self, exc: BaseException, *, failed_stage: str = "", failed_substage: str = "", context: dict | None = None):
        tb = traceback.format_exc()
        tb_frame = exc.__traceback__
        while tb_frame is not None and tb_frame.tb_next is not None: tb_frame = tb_frame.tb_next
        module = function = ""; line = None
        if tb_frame is not None:
            module = inspect.getmodule(tb_frame.tb_frame).__name__ if inspect.getmodule(tb_frame.tb_frame) else ""
            function = tb_frame.tb_frame.f_code.co_name; line = tb_frame.tb_lineno
        self.stage = "FAILED"; self.substage = failed_substage or self.substage
        payload = {"schema":"pyforestscan-prerun-failure-v1","attempt_id":self.root.name,"timestamp":datetime.now(timezone.utc).isoformat(),"failed_stage":failed_stage or self.stage,"failed_substage":self.substage,"exception_type":type(exc).__name__,"exception_message":str(exc),"module":module,"function":function,"line":line,"full_traceback":tb,"thread_id":self.thread_id,"thread_name":self.thread_name,**(context or {})}
        self._failure_payload = {"exception_type": type(exc).__name__, "exception_message": str(exc), "failed_stage": failed_stage or self.stage, "failed_substage": self.substage, "failure_module": module, "failure_function": function, "failure_line": line}
        try: atomic_write_json(self.root/"prerun_failure.json", payload)
        except OSError:
            try: (self.root/"prerun_failure.txt").write_text(tb,encoding="utf-8")
            except OSError: pass
        self._write()
