"""Execute one bounded EPT CHM child in a fresh managed Python process."""

from __future__ import annotations

import argparse
import os
import pickle
import traceback
import uuid
from pathlib import Path
import sys
from datetime import datetime, timezone

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))

from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.core.atomic_state import atomic_write_json


def _atomic_pickle(path: Path, value: object) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("wb") as stream:
        pickle.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run(payload_path: Path, result_path: Path) -> int:
    status_path = result_path.with_suffix(".status.json")
    started = __import__("time").monotonic()
    def progress(snapshot) -> None:
        message = str(getattr(snapshot, "message", "") or "Processing LiDAR")
        stage = (
            "Reading LiDAR" if "load" in message.lower() or "read" in message.lower()
            else "Calculating CHM" if "calculat" in message.lower()
            else "Writing Result" if "geotiff" in message.lower() or "raster" in message.lower()
            else "Preparing Data"
        )
        atomic_write_json(status_path, {
            "state": "running", "pid": os.getpid(), "stage": stage,
            "message": message, "percent": float(getattr(snapshot, "percent", 0.0)),
            "elapsed_seconds": __import__("time").monotonic() - started,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    try:
        with payload_path.open("rb") as stream:
            request = pickle.load(stream)
        atomic_write_json(status_path, {"state": "running", "pid": os.getpid(), "stage": "Reading LiDAR", "message": "Starting bounded LiDAR read.", "percent": 0, "updated_at": datetime.now(timezone.utc).isoformat()})
        result = PyForestScanAdapter(execution_mode="qgis_python", progress_sink=progress).create_chm(request)
        _atomic_pickle(result_path, result)
        atomic_write_json(status_path, {"state": "complete", "pid": os.getpid(), "stage": "Saving Checkpoint", "message": "Bounded result complete.", "percent": 100, "elapsed_seconds": __import__("time").monotonic() - started, "updated_at": datetime.now(timezone.utc).isoformat()})
        return 0
    except Exception as exc:
        atomic_write_json(result_path.with_suffix(".error.json"), {
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "payload": str(payload_path),
        })
        atomic_write_json(status_path, {"state": "failed", "pid": os.getpid(), "stage": "Needs Attention", "message": str(exc), "elapsed_seconds": __import__("time").monotonic() - started, "updated_at": datetime.now(timezone.utc).isoformat()})
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    return run(args.payload, args.result)


if __name__ == "__main__":
    raise SystemExit(main())
