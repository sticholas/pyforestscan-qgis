"""Own generic polygon preparation and product execution outside QGIS."""

from __future__ import annotations

import argparse
import os
import pickle
import threading
import time
import traceback
import uuid
from pathlib import Path

from pyforestscan_qgis.core.adapter import PyForestScanAdapter
from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.polygon_progress import progress_event


def _atomic_pickle(path: Path, value: object) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("wb") as stream:
        pickle.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_payload(payload_path: Path) -> int:
    with Path(payload_path).open("rb") as stream:
        payload = pickle.load(stream)
    report = payload["report"]
    job_dir = Path(payload["job_dir"])
    started = time.monotonic()
    source_id = str(report.selected_sources[0].path)
    state = progress_event(
        attempt_id=payload["attempt_id"], sequence=0,
        event_type="STAGE_TRANSITION", stage="COORDINATOR_STARTED",
        entity_type="dataset", entity_id=source_id,
        message="Managed process owns the polygon request.",
        total_datasets=len(report.selected_sources), total_products=len(report.request.products),
        last_forward_progress_at=time.time(),
    )
    heartbeat_sequence = 0
    stop = threading.Event()

    atomic_write_json(job_dir / "coordinator_identity.json", {
        "job_id": payload["job_id"], "attempt_id": payload["attempt_id"],
        "pid": os.getpid(), "parent_pid": os.getppid(), "started_at": time.time(),
        "runtime_executable": os.sys.executable, "request_path": str(payload_path),
    })

    def write_snapshot(event_type: str) -> None:
        atomic_write_json(job_dir / "progress_snapshot.json", {
            **state, "event_type": event_type, "active_stage": state["stage"],
            "heartbeat_sequence": heartbeat_sequence, "pid": os.getpid(),
            "elapsed_seconds": int(time.monotonic() - started),
            "last_heartbeat_at": time.time(),
        })

    def heartbeat() -> None:
        nonlocal heartbeat_sequence
        while not stop.wait(5):
            heartbeat_sequence += 1
            write_snapshot("HEARTBEAT")

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        os.environ["PYFORESTSCAN_GENERIC_POLYGON_COORDINATOR"] = "1"
        from pyforestscan_qgis.core.polygon_batch import execute_polygon_batch

        def stage(name: str, details: dict[str, object]) -> None:
            state.update(
                event_type="STAGE_TRANSITION", stage=name,
                message=str(details.get("operation", "Background processing continues.")),
                state=str(details.get("state", "RUNNING")),
            )
            state.update({key: value for key, value in details.items() if key != "state"})
            state["last_forward_progress_at"] = time.time()
            state["sequence"] += 1
            state["event_id"] = f'{payload["attempt_id"]}:{state["sequence"]}'
            write_snapshot("STAGE_TRANSITION")

        cancel_path = job_dir / "cancel_requested.json"
        pause_path = job_dir / "pause_requested.json"
        result = execute_polygon_batch(
            report, adapter=PyForestScanAdapter(execution_mode="qgis_python"),
            stage_callback=stage,
            control_callback=lambda: "cancel" if cancel_path.exists() else ("pause" if pause_path.exists() else None),
            attempt_folder=job_dir,
        )
        result_path = job_dir / "coordinator_result.pkl"
        _atomic_pickle(result_path, result)
        cancelled = cancel_path.exists()
        atomic_write_json(job_dir / "terminal_result.json", {
            "state": "cancelled" if cancelled else "complete",
            "result_path": str(result_path), "finished_at": time.time(),
        })
        return 1 if cancelled else 0
    except Exception as exc:
        cancelled = "cancelled" in str(exc).lower()
        atomic_write_json(job_dir / "terminal_result.json", {
            "state": "cancelled" if cancelled else "failed", "error": str(exc),
            "traceback": traceback.format_exc(), "finished_at": time.time(),
        })
        return 1
    finally:
        stop.set()
        thread.join(timeout=1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    return run_payload(parser.parse_args().payload)


if __name__ == "__main__":
    raise SystemExit(main())
