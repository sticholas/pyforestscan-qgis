"""Native PBM worker exit classification and parent-owned diagnostics."""
from __future__ import annotations
import json,os
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from pathlib import Path

WINDOWS_EXCEPTION_NAMES={0xC0000005:"ACCESS_VIOLATION",0xC000001D:"ILLEGAL_INSTRUCTION",0xC0000409:"STACK_BUFFER_OVERRUN"}

@dataclass(frozen=True)
class NativeWorkerExit:
    native_crash:bool;exit_code:int;unsigned_exit_code:int;exception_status:str;error_code:str;user_message:str;technical_message:str
    def to_dict(self):return asdict(self)

def classify_worker_exit(returncode:int,result_exists:bool,stderr:str=""):
    unsigned=returncode & 0xFFFFFFFF
    exception=WINDOWS_EXCEPTION_NAMES.get(unsigned,"")
    native=bool(exception or returncode<0 or (os.name=="nt" and unsigned>=0xC0000000))
    if native:
        status=f"0x{unsigned:08X}";name=exception or "NATIVE_EXCEPTION"
        return NativeWorkerExit(True,returncode,unsigned,status,"NATIVE_BACKEND_CRASH","The managed LiDAR worker stopped because a native processing library crashed.",f"Native worker exit {status} ({name}); structured_result_exists={result_exists}.")
    return NativeWorkerExit(False,returncode,unsigned,"","","",f"Worker exited with code {returncode}; structured_result_exists={result_exists}.")

def write_native_crash_bundle(run_folder:Path,*,exit_info:NativeWorkerExit,command:list[str],executable:Path,pid:int|None,stdout:str,stderr:str,heartbeat:dict|None=None):
    diagnostics=Path(run_folder)/"diagnostics";diagnostics.mkdir(parents=True,exist_ok=True)
    payload={"timestamp":datetime.now(timezone.utc).isoformat(),"pid":pid,"executable":str(executable),"command":command,"exit":exit_info.to_dict(),"heartbeat":heartbeat or {}}
    _write_json(diagnostics/"process_exit.json",exit_info.to_dict());_write_json(diagnostics/"terminal_event.json",payload);_write_json(diagnostics/"command.json",{"executable":str(executable),"arguments":command[1:]});(diagnostics/"stdout_tail.txt").write_text(_tail(stdout),encoding="utf-8");(diagnostics/"stderr_tail.txt").write_text(_tail(stderr),encoding="utf-8")
    return diagnostics

def _write_json(path,payload):
    temporary=path.with_suffix(".tmp");temporary.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8");temporary.replace(path)
def _tail(text,limit=16384):return (text or "")[-limit:]
