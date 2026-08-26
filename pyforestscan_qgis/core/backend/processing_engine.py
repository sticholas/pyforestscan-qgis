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
from .process_env import build_processing_engine_environment, hidden_subprocess_kwargs
from .runtime_manifest import PRODUCT_CAPABILITIES

PROCESSING_ENGINE_CONTRACT_VERSION = "2"
REQUIRED_PYFORESTSCAN_MODULES = (
    "pyforestscan",
    "pyforestscan.handlers",
    "pyforestscan.calculate",
    "pyforestscan.filters",
    "pyforestscan.process",
)


class ProcessingEngineState(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
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


@dataclass(frozen=True)
class ProcessingRuntimeToken:
    executable: str
    environment_fingerprint: str
    contract_hash: str
    protocol: str
    verified_at: str
    product_capability_hash: str
    engine_id: str = ""
    backend_runner_hash: str = ""
    plugin_build_id: str = ""
    dependency_manifest_hash: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "ProcessingRuntimeToken | None":
        if not value:
            return None
        return cls(**{field: str(value.get(field, "")) for field in cls.__dataclass_fields__})


@dataclass(frozen=True)
class ProcessingEngineStateModel:
    status: ProcessingEngineState
    last_verified: str
    contract_hash: str
    engine_version: str
    setup_needed: bool
    repair_needed: bool
    runtime_available: bool
    message: str
    engine_id: str = ""
    executable: str = ""
    environment_fingerprint: str = ""
    protocol_version: str = ""
    backend_runner_hash: str = ""
    plugin_build_id: str = ""
    product_capability_hash: str = ""
    dependency_manifest_hash: str = ""
    ready_for_processing: bool = False
    failure_code: str = ""
    runtime_token: ProcessingRuntimeToken | None = None

    @classmethod
    def from_report(cls, report: ProcessingEngineReport) -> "ProcessingEngineStateModel":
        contract = report.contract
        token = _token_from_contract(contract) if report.ready else None
        return cls(
            report.state,
            str(contract.get("verified_at", "")),
            contract_hash(contract) if contract else "",
            str(contract.get("versions", {}).get("pyforestscan", "unknown")),
            report.state is ProcessingEngineState.SETUP_REQUIRED,
            report.state in {ProcessingEngineState.REPAIR_REQUIRED, ProcessingEngineState.INCOMPATIBLE},
            report.ready,
            report.summary,
            str(contract.get("engine_id", "")),
            report.executable,
            str(contract.get("environment_fingerprint", "")),
            str(contract.get("protocol_version", "")),
            str(contract.get("runner_sha256", "")),
            str(contract.get("plugin_build_id", "")),
            str(contract.get("product_capability_hash", "")),
            str(contract.get("dependency_manifest_hash", "")),
            report.ready,
            "" if report.ready else _failure_code(report.state),
            token,
        )


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
    candidates = (paths.python_executable, paths.config_file, *_critical_runtime_files(paths))
    for candidate in candidates:
        digest.update(str(candidate).encode("utf-8"))
        try:
            stat = candidate.stat()
        except OSError:
            digest.update(b"missing")
        else:
            digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
    return digest.hexdigest()


def _critical_runtime_files(paths: BackendPaths) -> tuple[Path, ...]:
    """Return inexpensive package sentinels that invalidate stale READY manifests."""
    roots = [paths.environment_path / "Lib" / "site-packages"]
    roots.extend((paths.environment_path / "lib").glob("python*/site-packages"))
    relative = (
        Path("pyforestscan/__init__.py"), Path("pyforestscan/handlers.py"),
        Path("pyforestscan/calculate.py"), Path("pyforestscan/filters.py"),
        Path("pyforestscan/process.py"), Path("pdal/__init__.py"),
        Path("rasterio/__init__.py"), Path("numpy/__init__.py"),
        Path("scipy/__init__.py"), Path("shapely/__init__.py"),
        Path("pyproj/__init__.py"), Path("pandas/__init__.py"),
        Path("osgeo/gdal.py"),
    )
    return tuple(root / item for root in roots for item in relative)


def contract_hash(contract: dict[str, Any]) -> str:
    """Hash stable runtime identity and capability fields, excluding process-local data."""
    stable = {
        key: contract.get(key)
        for key in (
            "backend_api_version", "protocol_version", "plugin_version", "runner_sha256",
            "plugin_build_id",
            "python_version", "python_executable", "versions", "module_locations",
            "required_functions", "required_function_signatures", "product_capabilities",
            "capability_smoke_results", "dependency_manifest_hash", "product_capability_hash",
        )
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def product_capability_hash(products: tuple[str, ...]) -> str:
    payload = {name: PRODUCT_CAPABILITIES.get(name, ()) for name in sorted(set(products))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def dependency_manifest_hash() -> str:
    from .runtime_manifest import PROCESSING_ENGINE_DEPENDENCIES

    payload = [asdict(item) for item in PROCESSING_ENGINE_DEPENDENCIES]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def engine_id(paths: BackendPaths) -> str:
    return hashlib.sha256(str(paths.environment_path.resolve()).encode("utf-8")).hexdigest()[:20]


def current_plugin_build_id() -> str:
    """Hash the packaged runner and launch surfaces without importing QGIS."""
    package_root = Path(__file__).resolve().parents[2]
    inputs = (
        package_root / "backend_runner" / "run_processing_job.py",
        package_root / "core" / "adapter.py",
        package_root / "core" / "pipeline.py",
    )
    try:
        return hashlib.sha256(b"".join(path.read_bytes() for path in inputs)).hexdigest()
    except OSError:
        return ""


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
        packaged_build = current_plugin_build_id()
        stale = (
            payload.get("contract_version") != PROCESSING_ENGINE_CONTRACT_VERSION
            or payload.get("environment_fingerprint") != environment_fingerprint(self.paths)
            or not packaged_build
            or payload.get("plugin_build_id") != packaged_build
        )
        if stale:
            return ProcessingEngineReport(ProcessingEngineState.CHECKING, "Processing Engine verification is stale.", str(self.paths.python_executable), payload)
        state = ProcessingEngineState(payload.get("status", ProcessingEngineState.CHECKING.value))
        return ProcessingEngineReport(state, _summary_for_state(state), str(self.paths.python_executable), payload, tuple(payload.get("failed_components", ())), True)

    def verify(self, *, persist: bool = True) -> ProcessingEngineReport:
        if not self.paths.python_executable.exists():
            return ProcessingEngineReport(ProcessingEngineState.SETUP_REQUIRED, "Processing setup required.", str(self.paths.python_executable), {})
        command = [str(self.paths.python_executable), "-m", "pyforestscan_qgis.backend_runner", "inspect_runtime_contract"]
        env = build_processing_engine_environment(self.paths.environment_path, self.paths.platform.value)
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
            "engine_id": engine_id(self.paths),
            "dependency_manifest_hash": dependency_manifest_hash(),
            "product_capability_hash": product_capability_hash(tuple(PRODUCT_CAPABILITIES)),
        }
        if persist:
            path = processing_engine_manifest_path(self.paths)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
                os.replace(temporary, path)
            except OSError as exc:
                payload["cache_write_error"] = str(exc)
                failures += ("manifest_persistence",)
                state = ProcessingEngineState.FAILED
                payload["status"] = state.value
                payload["failed_components"] = list(failures)
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

    def assert_ready_for(self, products: tuple[str, ...]) -> ProcessingRuntimeToken:
        report = self.require_ready()
        unsupported = tuple(product for product in products if product not in PRODUCT_CAPABILITIES and product not in {"dataset_inspection", "ept_subset_extract"})
        if unsupported:
            raise ProcessingEngineError("ENGINE_PRODUCT_UNSUPPORTED", "Processing Engine does not support the selected product.", ", ".join(unsupported))
        return _token_from_contract(report.contract, products)

    def validate_token(self, token: ProcessingRuntimeToken, products: tuple[str, ...]) -> None:
        current = self.assert_ready_for(products)
        if current.executable != token.executable or current.environment_fingerprint != token.environment_fingerprint or current.contract_hash != token.contract_hash or current.protocol != token.protocol or current.product_capability_hash != token.product_capability_hash:
            raise ProcessingEngineError("ENGINE_RUNTIME_CHANGED", "Processing Engine needs rechecking before this job can start.")


class ProcessingEngineService:
    """Single state, setup, contract, token, and environment facade."""

    def __init__(self, paths: BackendPaths, setup_callback: Callable[..., Any] | None = None) -> None:
        self.paths = paths
        self.verifier = ProcessingEngineVerifier(paths)
        self.setup_callback = setup_callback
        self._state: ProcessingEngineStateModel | None = None
        self._listeners: list[Callable[[ProcessingEngineStateModel], None]] = []

    def state(self, *, quick: bool = True) -> ProcessingEngineStateModel:
        if quick and self._state is not None:
            return self._state
        report = self.verifier.quick() if quick else self.verifier.verify()
        return self._publish(report)

    def assert_ready_for(self, products: tuple[str, ...]) -> ProcessingRuntimeToken:
        return self.runtime_token_for(products)

    def runtime_token_for(self, products: tuple[str, ...]) -> ProcessingRuntimeToken:
        """Return a token derived from the one published READY manifest."""
        state = self.state(quick=True)
        if not state.ready_for_processing:
            state = self.state(quick=False)
        if not state.ready_for_processing or state.runtime_token is None:
            raise ProcessingEngineError(state.failure_code or "ENGINE_REPAIR_REQUIRED", state.message)
        if state.environment_fingerprint != environment_fingerprint(self.paths):
            report = ProcessingEngineReport(
                ProcessingEngineState.REPAIR_REQUIRED,
                "Processing Engine changed after verification.",
                str(self.paths.python_executable),
                state.runtime_token.to_dict(),
                ("environment_fingerprint",),
            )
            self._publish(report)
            raise ProcessingEngineError("ENGINE_RUNTIME_CHANGED", report.summary)
        unsupported = tuple(product for product in products if product not in PRODUCT_CAPABILITIES and product not in {"dataset_inspection", "ept_subset_extract"})
        if unsupported:
            raise ProcessingEngineError("ENGINE_PRODUCT_UNSUPPORTED", "Processing Engine does not support the selected product.", ", ".join(unsupported))
        token = state.runtime_token
        return ProcessingRuntimeToken(
            engine_id=token.engine_id,
            executable=token.executable,
            environment_fingerprint=token.environment_fingerprint,
            contract_hash=token.contract_hash,
            protocol=token.protocol,
            verified_at=token.verified_at,
            product_capability_hash=product_capability_hash(products),
            backend_runner_hash=token.backend_runner_hash,
            plugin_build_id=token.plugin_build_id,
            dependency_manifest_hash=token.dependency_manifest_hash,
        )

    def environment(self) -> dict[str, str]:
        return build_processing_engine_environment(self.paths.environment_path, self.paths.platform.value)

    def setup_or_repair(self, progress_callback=None) -> ProcessingEngineStateModel:
        current = self.verifier.verify(persist=False)
        if current.ready:
            return self._publish(self.verifier.verify())
        if self.setup_callback is None:
            raise ProcessingEngineError("ENGINE_SETUP_REQUIRED", "Processing Engine setup is not available.")
        with ProcessingEngineSetupLock(self.paths):
            self.setup_callback(progress_callback=progress_callback)
            final = self.verifier.verify()
            state = self._publish(final)
            if not state.ready_for_processing:
                raise ProcessingEngineError(state.failure_code or "ENGINE_REPAIR_REQUIRED", state.message, ", ".join(final.failed_components))
            return state

    def subscribe(self, listener: Callable[[ProcessingEngineStateModel], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def recheck(self) -> ProcessingEngineStateModel:
        return self._publish(self.verifier.verify())

    def _publish(self, report: ProcessingEngineReport) -> ProcessingEngineStateModel:
        state = ProcessingEngineStateModel.from_report(report)
        self._state = state
        for listener in tuple(self._listeners):
            listener(state)
        return state


def _token_from_contract(contract: dict[str, Any], products: tuple[str, ...] | None = None) -> ProcessingRuntimeToken:
    return ProcessingRuntimeToken(
        engine_id=str(contract.get("engine_id", "")),
        executable=str(contract.get("python_executable", "")),
        environment_fingerprint=str(contract.get("environment_fingerprint", "")),
        contract_hash=contract_hash(contract),
        protocol=str(contract.get("protocol_version", "")),
        verified_at=str(contract.get("verified_at", "")),
        product_capability_hash=product_capability_hash(products or tuple(PRODUCT_CAPABILITIES)),
        backend_runner_hash=str(contract.get("runner_sha256", "")),
        plugin_build_id=str(contract.get("plugin_build_id", "")),
        dependency_manifest_hash=str(contract.get("dependency_manifest_hash", "")),
    )


def _failure_code(state: ProcessingEngineState) -> str:
    return {
        ProcessingEngineState.SETUP_REQUIRED: "ENGINE_SETUP_REQUIRED",
        ProcessingEngineState.REPAIR_REQUIRED: "ENGINE_REPAIR_REQUIRED",
        ProcessingEngineState.INCOMPATIBLE: "ENGINE_UPDATE_REQUIRED",
        ProcessingEngineState.FAILED: "ENGINE_VERIFICATION_FAILED",
    }.get(state, "ENGINE_NOT_READY")


def _summary_for_state(state: ProcessingEngineState) -> str:
    return {
        ProcessingEngineState.UNINITIALIZED: "Processing Engine has not been checked.",
        ProcessingEngineState.READY: "Processing Engine is ready.",
        ProcessingEngineState.CHECKING: "Processing Engine needs verification.",
        ProcessingEngineState.SETUP_REQUIRED: "Processing setup required.",
        ProcessingEngineState.UPDATING: "Processing Engine is being prepared.",
        ProcessingEngineState.REPAIR_REQUIRED: "PyForestScan's Processing Engine needs repair.",
        ProcessingEngineState.INCOMPATIBLE: "Processing Engine needs an update.",
        ProcessingEngineState.FAILED: "Processing Engine check failed.",
    }[state]
