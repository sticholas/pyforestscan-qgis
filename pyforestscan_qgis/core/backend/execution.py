"""Controlled PBM processing execution service."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pyforestscan_qgis.backend_runner.job_result import BackendJobResult
from pyforestscan_qgis.backend_runner.job_spec import BackendJobSpec, build_job_spec_from_request

from .logging import backend_log_path, write_backend_log_entry
from .models import BackendStatus, BackendVerificationResult
from .paths import BackendPaths
from .process_env import build_clean_subprocess_env, clean_env_summary, summarize_subprocess_output

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

GUI_EXECUTABLE_MARKERS = (
    "qgis-ltr-bin",
    "qgis-bin",
    "qgis.exe",
    "qgis-ltr.exe",
    "qgis_process",
)


@dataclass(frozen=True)
class BackendExecutionAvailability:
    """Readiness to run PBM processing jobs."""

    ready: bool
    message: str
    backend_python: Path | None = None


class BackendExecutionService:
    """Run managed PyForestScan jobs through PBM backend Python."""

    def __init__(
        self,
        paths: BackendPaths,
        verifier: Callable[[], BackendVerificationResult],
        runner: CommandRunner | None = None,
        timeout_seconds: int = 3600,
        plugin_parent: Path | None = None,
    ) -> None:
        self.paths = paths
        self.verifier = verifier
        self.runner = runner or subprocess.run
        self.timeout_seconds = timeout_seconds
        self.plugin_parent = plugin_parent or Path(__file__).resolve().parents[3]
        self.log_path = backend_log_path("execute", paths.logs_dir)

    def can_execute_processing(self) -> BackendExecutionAvailability:
        """Return whether PBM backend processing can run now."""
        verification = self.verifier()
        if verification.status is not BackendStatus.READY:
            return BackendExecutionAvailability(False, f"PBM backend is not ready: {verification.summary}", self.paths.python_executable)
        ok, message = validate_backend_python_executable(self.paths.python_executable)
        return BackendExecutionAvailability(ok, message, self.paths.python_executable)

    def verify_runner(self) -> BackendExecutionAvailability:
        """Verify that the backend runner module can be imported by backend Python."""
        availability = self.can_execute_processing()
        if not availability.ready:
            return availability
        command = self.runner_command_for_args(("--help",))
        try:
            completed = self.runner(command, check=False, capture_output=True, text=True, timeout=30, cwd=str(self.plugin_parent), env=build_clean_subprocess_env(prepend_paths=(self.paths.python_executable.parent,)))
        except Exception as exc:  # noqa: BLE001 - report safely to UI/tests.
            return BackendExecutionAvailability(False, f"PBM runner verification failed: {exc}", self.paths.python_executable)
        if completed.returncode != 0:
            output = summarize_subprocess_output(completed.stderr, completed.stdout)
            return BackendExecutionAvailability(False, f"PBM runner verification failed: {output}", self.paths.python_executable)
        return BackendExecutionAvailability(True, "PBM backend runner is importable.", self.paths.python_executable)

    def write_job_spec(self, product: str, request: Any, run_folder: Path | None = None) -> Path:
        """Build and write one job spec for a product request."""
        spec = build_job_spec_from_request(product, request, run_folder=run_folder)
        return spec.write()

    def read_job_result(self, result_path: Path) -> BackendJobResult:
        """Read a backend job result JSON file."""
        return BackendJobResult.read(result_path)

    def run_product(self, product: str, request: Any) -> BackendJobResult:
        """Run a product request through the managed backend."""
        spec = build_job_spec_from_request(product, request)
        spec_path = spec.write()
        return self.run_processing_job(spec, spec_path)

    def run_processing_job(self, spec: BackendJobSpec, spec_path: Path | None = None) -> BackendJobResult:
        """Run one PBM backend job spec and return the structured result."""
        availability = self.can_execute_processing()
        if not availability.ready:
            raise RuntimeError(availability.message)
        path = spec_path or spec.write()
        command = self.runner_command(path)
        write_backend_log_entry(
            self.log_path,
            "execute",
            "Starting PBM backend processing job.",
            stage="START",
            details={**clean_env_summary("backend_runner", self.paths.python_executable), "backend_python": str(self.paths.python_executable), "spec": str(path), "product": spec.product},
        )
        try:
            completed = self.runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(self.plugin_parent),
                env=build_clean_subprocess_env(prepend_paths=(self.paths.python_executable.parent,)),
            )
        except subprocess.TimeoutExpired as exc:
            write_backend_log_entry(self.log_path, "execute", f"PBM backend job timed out: {exc}", level="ERROR", stage="TIMEOUT")
            raise RuntimeError(f"PBM backend job timed out after {self.timeout_seconds} seconds.") from exc
        except Exception as exc:  # noqa: BLE001 - convert subprocess errors at service boundary.
            write_backend_log_entry(self.log_path, "execute", f"PBM backend job failed to start: {exc}", level="ERROR", stage="START")
            raise RuntimeError(f"PBM backend job failed to start: {exc}") from exc

        if not spec.result_path.exists():
            message = summarize_subprocess_output(completed.stderr, completed.stdout) or "PBM backend runner did not write a result file."
            write_backend_log_entry(self.log_path, "execute", message, level="ERROR", stage="RESULT", details={"returncode": completed.returncode})
            raise RuntimeError(message)
        result = BackendJobResult.read(spec.result_path)
        result = BackendJobResult(
            job_id=result.job_id,
            product=result.product,
            status=result.status,
            outputs=result.outputs,
            warnings=result.warnings,
            errors=result.errors,
            started_at=result.started_at,
            finished_at=result.finished_at,
            product_metrics=result.product_metrics,
            stdout=completed.stdout or result.stdout,
            stderr=completed.stderr or result.stderr,
            traceback=result.traceback,
        )
        level = "INFO" if result.success and completed.returncode == 0 else "ERROR"
        write_backend_log_entry(
            self.log_path,
            "execute",
            "PBM backend processing job completed." if level == "INFO" else "PBM backend processing job failed.",
            level=level,
            stage="FINISH",
            details={"returncode": completed.returncode, "result": str(spec.result_path), "backend_python": str(self.paths.python_executable)},
        )
        if completed.returncode != 0 or not result.success:
            raise RuntimeError("; ".join(result.errors) or summarize_subprocess_output(completed.stderr, completed.stdout) or "PBM backend job failed.")
        return result

    def runner_command(self, spec_path: Path) -> list[str]:
        """Return the backend runner command for a spec path."""
        return self.runner_command_for_args(("--spec", str(spec_path)))

    def runner_command_for_args(self, args: tuple[str, ...]) -> list[str]:
        """Return the backend runner command for arbitrary module args."""
        ok, message = validate_backend_python_executable(self.paths.python_executable)
        if not ok:
            raise RuntimeError(message)
        return [str(self.paths.python_executable), "-m", "pyforestscan_qgis.backend_runner.run_processing_job", *args]


def validate_backend_python_executable(path: Path) -> tuple[bool, str]:
    """Refuse QGIS GUI executables and require a Python-looking backend executable."""
    text = str(path).lower().replace("\\", "/")
    name = path.name.lower()
    if any(marker in text for marker in GUI_EXECUTABLE_MARKERS):
        return False, f"Refusing to use QGIS GUI executable as PBM backend Python: {path}"
    if name not in {"python", "python.exe", "python3", "python3.exe"}:
        return False, f"PBM backend executable must be backend Python, not {path.name}."
    if not path.exists():
        return False, f"PBM backend Python does not exist: {path}"
    return True, f"PBM backend Python is safe to execute: {path}"
