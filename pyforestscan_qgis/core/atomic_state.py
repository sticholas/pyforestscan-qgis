"""Crash-safe JSON state persistence for backend jobs."""
from __future__ import annotations
import json, os, time, uuid
from pathlib import Path
from typing import Any

def atomic_write_json(path: Path | str, payload: Any, *, retries: int = 3) -> Path:
    destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True)
    encoded=(json.dumps(payload,indent=2,sort_keys=True)+"\n").encode("utf-8");last_error=None
    for attempt in range(max(1,retries)):
        temporary=destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(encoded);stream.flush();os.fsync(stream.fileno())
            if temporary.stat().st_size!=len(encoded):raise OSError("Atomic JSON temporary file has an unexpected length.")
            json.loads(temporary.read_text(encoding="utf-8"));os.replace(temporary,destination)
            json.loads(destination.read_text(encoding="utf-8"));return destination
        except OSError as exc:
            last_error=exc;temporary.unlink(missing_ok=True)
            if attempt+1<max(1,retries):time.sleep(.05*(attempt+1))
    raise last_error or OSError(f"Could not write {destination}")

def remove_invalid_temporaries(folder: Path | str) -> tuple[Path,...]:
    removed=[];root=Path(folder)
    if not root.exists():return ()
    for path in root.rglob("*.tmp"):
        try:valid=path.stat().st_size>0 and isinstance(json.loads(path.read_text(encoding="utf-8")),(dict,list))
        except (OSError,ValueError):valid=False
        if not valid:path.unlink(missing_ok=True);removed.append(path)
    return tuple(removed)
