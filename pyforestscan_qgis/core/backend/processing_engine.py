"""Authoritative readiness contract for the managed processing engine."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .paths import BackendPaths
from .process_env import (
    build_clean_subprocess_env,
    conda_environment_data_env,
    conda_environment_path_entries,
    hidden_subprocess_kwargs,
)

PROCESSING_ENGINE_CONTRACT_VERSION = "1"
REQUIRED_PYFORESTSCAN_MODULES = (
    "pyforestscan",
    "pyforestscan.handlers",
    "pyforestscan.calculate",
    "pyforestscan.filters",
    "pyforestscan.process",
)


class ProcessingEngineState(str, Enum):
    READY = "READY"
    CHECKING = "CHECKING"
    SETUP_REQUIRED = "SETUP_REQUIRED"
    UPDATING = "UPDATING"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    INCOMPATIBLE = "INCOMPATIBLE"
    FAILED = "FAILED"


class ProcessingEngineError(RuntimeError):
    """A setup/runtime problem detected before scientific job creation."""

    def __init__(self, code: str, message: str, technical_message: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.technical_message = technical_message or message


@dataclass(frozen=True)
class ProcessingEngineReport:
    state: ProcessingEngineState
    summary: str
    executable: str
    contract: dict[str, Any]
    failed_components: tuple[str, ...] = ()
    from_cache: bool = False

    @property
    def ready(self) -> bool:
        return self.state is ProcessingEngineState.READY


def processing_engine_manifest_path(paths: BackendPaths) -> Path:
    return paths.backend_root / "processing_engine.json"


class ProcessingEngineSetupLock:
    """Cross-process lock preventing two QGIS sessions from modifying one engine."""

    def __init__(self, paths: BackendPaths) -> None:
        self.path = paths.backend_root / "processing_engine.setup.lock"
        self._fd: int | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        os.write(self._fd, json.dumps({"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}).encode("utf-8"))
        return True

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self):
        if not self.acquire():
            raise ProcessingEngineError("ENGINE_BUSY", "Processing Engine is being prepared by another QGIS session.")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()


def environment_fingerprint(paths: BackendPaths) -> str:
    """Fingerprint execution-critical files without importing scientific packages."""
    digest = hashlib.sha256()
    candidates = (paths.python_executable, paths.config_file)
    for candidate in candidates:
        digest.update(str(candidate).encode("utf-8"))
        try:
            stat = candidate.stat()
        except OSError:
            digest.update(b"missing")
        else:
            digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
    return digest.hexdigest()


class ProcessingEngineVerifier:
    """Verify the same managed interpreter used for scientific execution."""

    def __init__(self, paths: BackendPaths, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None, plugin_parent: Path | None = None) -> None:
        self.paths = paths
        self.runner = runner or subprocess.run
        self.plugin_parent = plugin_parent or Path(__file__).resolve().parents[3]

    def quick(self) -> ProcessingEngineReport:
        """Use the persisted manifest only when its environment fingerprint is current."""
        if not self.paths.python_executable.exists():
            return ProcessingEngineReport(ProcessingEngineState.SETUP_REQUIRED, "Processing setup required.", str(self.paths.python_executable), {})
        path = processing_engine_manifest_path(self.paths)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ProcessingEngineReport(ProcessingEngineState.CHECKING, "Processing Engine needs verification.", str(self.paths.python_executable), {})
        if payload.get("contract_version") != PROCESSING_ENGINE_CONTRACT_VERSION or payload.get("environment_fingerprint") != environment_fingerprint(self.paths):
            return ProcessingEngineReport(ProcessingEngineState.CHECKING, "Processing Engine verification is stale.", str(self.paths.python_executable), payload)
        state = ProcessingEngineState(payload.get("status", ProcessingEngineState.CHECKING.value))
        return ProcessingEngineReport(state, _summary_for_state(state), str(self.paths.python_executable), payload, tuple(payload.get("failed_components", ())), True)

    def verify(self, *, persist: bool = True) -> ProcessingEngineReport:
        if not self.paths.python_executable.exists():
            return ProcessingEngineReport(ProcessingEngineState.SETUP_REQUIRED, "Processing setup required.", str(self.paths.python_executable), {})
        command = [str(self.paths.python_executable), "-m", "pyforestscan_qgis.backend_runner", "inspect_runtime_contract"]
        env = build_clean_subprocess_env(
            prepend_paths=conda_environment_path_entries(self.paths.environment_path, self.paths.platform.value),
            extra_env=conda_environment_data_env(self.paths.environment_path, self.paths.platform.value),
        )
        try:
            completed = self.runner(command, check=False, capture_output=True, text=True, timeout=180, cwd=str(self.plugin_parent), env=env, **hidden_subprocess_kwargs())
            contract = json.loads(completed.stdout or "{}")
        except Exception as exc:  # noqa: BLE001 - state boundary must be actionable.
            return ProcessingEngineReport(ProcessingEngineState.FAILED, "Processing Engine check failed.", str(self.paths.python_executable), {}, (str(exc),))
        failures = tuple(str(item) for item in contract.get("failed_required_components", ()))
        actual = str(contract.get("python_executable", ""))
        if actual and Path(actual).resolve() != self.paths.python_executable.resolve():
            failures += ("runtime_identity",)
        protocol_ok = bool(contract.get("protocol_compatible", False))
        if not protocol_ok:
            state = ProcessingEngineState.INCOMPATIBLE
        elif failures or completed.returncode != 0:
            state = ProcessingEngineState.REPAIR_REQUIRED
        else:
            state = ProcessingEngineState.READY
        payload = {
            **contract,
            "contract_version": PROCESSING_ENGINE_CONTRACT_VERSION,
            "environment_fingerprint": environment_fingerprint(self.paths),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "status": state.value,
            "failed_components": list(failures),
        }
        if persist:
            path = processing_engine_manifest_path(self.paths)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
                os.replace(temporary, path)
            except OSError as exc:
                # Cache persistence accelerates startup but is not the runtime authority.
                payload["cache_write_error"] = str(exc)
        return ProcessingEngineReport(state, _summary_for_state(state), str(self.paths.python_executable), payload, failures)

    def require_ready(self) -> ProcessingEngineReport:
        report = self.verify()
        if report.ready:
            return report
        code = {
            ProcessingEngineState.SETUP_REQUIRED: "ENGINE_SETUP_REQUIRED",
            ProcessingEngineState.REPAIR_REQUIRED: "ENGINE_REPAIR_REQUIRED",
            ProcessingEngineState.INCOMPATIBLE: "ENGINE_PROTOCOL_MISMATCH",
        }.get(report.state, "ENGINE_IMPORT_FAILED")
        raise ProcessingEngineError(code, _summary_for_state(report.state), ", ".join(report.failed_components))


def _summary_for_state(state: ProcessingEngineState) -> str:
    return {
        ProcessingEngineState.READY: "Processing Engine is ready.",
        ProcessingEngineState.CHECKING: "Processing Engine needs verification.",
        ProcessingEngineState.SETUP_REQUIRED: "Processing setup required.",
        ProcessingEngineState.UPDATING: "Processing Engine is being prepared.",
        ProcessingEngineState.REPAIR_REQUIRED: "PyForestScan's Processing Engine needs repair.",
        ProcessingEngineState.INCOMPATIBLE: "Processing Engine needs an update.",
        ProcessingEngineState.FAILED: "Processing Engine check failed.",
    }[state]
