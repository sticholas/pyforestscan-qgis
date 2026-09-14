"""Run one bounded polygon preparation operation in an owned PBM child."""

from __future__ import annotations

import argparse
import os
import pickle
import traceback
import uuid
from pathlib import Path

from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.core.atomic_state import atomic_write_json


def _atomic_pickle(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("wb") as stream:
        pickle.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_payload(payload_path: Path) -> int:
    with payload_path.open("rb") as stream:
        payload = pickle.load(stream)
    terminal = Path(payload["terminal_path"])
    result_path = Path(payload["result_path"])
    try:
        result = PyForestScanAdapter(execution_mode="qgis_python").normalize_heights(payload["request"])
        _atomic_pickle(result_path, result)
        atomic_write_json(terminal, {"state": "complete", "result_path": str(result_path), "pid": os.getpid()})
        return 0
    except Exception as exc:
        atomic_write_json(terminal, {"state": "failed", "error": str(exc), "traceback": traceback.format_exc(), "pid": os.getpid()})
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    return run_payload(parser.parse_args().payload)


if __name__ == "__main__":
    raise SystemExit(main())
