"""Real managed-indexer cancellation/retry QA against an immutable small source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.backend.service import BackendService
from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
from pyforestscan_qgis.core.atomic_state import atomic_write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.source.stat().st_size > 100_000_000:
        raise ValueError("Use a bounded small raw cloud above the direct threshold.")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    engine = BackendService().processing_engine_service()
    token = engine.runtime_token_for(("dataset_inspection",))
    script = Path(__file__).resolve().parents[2] / "pyforestscan_qgis/viewer/prepare_source.py"
    cancel = args.output_dir / "cancel"
    progress = args.output_dir / "progress.json"
    cache = args.output_dir / "cache"
    def digest():
        with args.source.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"source": str(args.source), "before": digest()}
    command = [token.executable, "-I", str(script), "--source", str(args.source),
               "--cache", str(cache), "--progress-file", str(progress), "--cancel-file", str(cancel)]
    process = None
    try:
        with (args.output_dir / "cancel-stdout.log").open("w") as out, (args.output_dir / "cancel-stderr.log").open("w") as err:
            process = subprocess.Popen(command, env=engine.environment(), stdout=out, stderr=err,
                                       **hidden_subprocess_kwargs())
            start = time.monotonic()
            while process.poll() is None:
                if time.monotonic() - start > 60:
                    raise TimeoutError("Indexer did not start in the QA deadline.")
                try:
                    status = json.loads(progress.read_text())
                except (OSError, ValueError):
                    status = {}
                if status.get("indexer_pid"):
                    report["indexer_pid"] = status["indexer_pid"]
                    cancelled_at = time.monotonic()
                    cancel.touch()
                    process.wait(timeout=30)
                    report["cancel_seconds"] = time.monotonic() - cancelled_at
                    break
                time.sleep(.05)
        assert report.get("indexer_pid"), "The test did not reach a running indexer."
        assert process.returncode, "Cancelled preparation incorrectly succeeded."
        assert not list(cache.glob("*/temp")), "Cancelled scratch remains."
        assert not list(cache.glob("*/build.lock")), "Cancelled build lock remains."
        assert not list(cache.glob("*/view.copc.laz")), "Cancelled cache was published."
        from pyforestscan_qgis.core.point_cloud.view_cache import process_alive
        assert not process_alive(report["indexer_pid"]), "Cancelled indexer is still alive."
        report["cancel_clean"] = True
        cancel.unlink()
        retry = subprocess.run(command, env=engine.environment(), capture_output=True, text=True,
                               timeout=90, **hidden_subprocess_kwargs())
        assert retry.returncode == 0, retry.stderr
        report["retry"] = json.loads(retry.stdout.splitlines()[-1])
        report["after"] = digest()
        assert report["before"] == report["after"], "Original changed."
        report["passed"] = True
    except Exception as error:
        report.update(passed=False, error=str(error))
    finally:
        if process is not None and process.poll() is None:
            from pyforestscan_qgis.core.owned_workers import terminate_process_tree
            terminate_process_tree(process)
            process.wait()
        atomic_write_json(args.output_dir / "cancellation.json", report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
