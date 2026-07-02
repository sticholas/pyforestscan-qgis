"""Service facade for the PyForestScan Backend Manager."""

from __future__ import annotations

from pathlib import Path

from .config import load_backend_config, planned_backend_config
from .install_plan import BackendInstallPlan, create_backend_install_plan, format_install_plan
from .logging import read_backend_log, write_backend_log_entry
from .models import BackendOperationResult, BackendRegistry, BackendState, BackendStatus, BackendVerificationResult
from .paths import BackendPaths, resolve_backend_paths
from .registry import default_backend_registry
from .state import detect_backend_state
from .verification import format_verification_result, verify_backend


class BackendService:
    """Detect, verify, and preview the planned user-local PyForestScan backend."""

    def __init__(self, paths: BackendPaths | None = None, registry: BackendRegistry | None = None) -> None:
        """Create a backend service using resolved paths and registry data."""
        self.paths = paths or resolve_backend_paths()
        self.registry = registry or default_backend_registry()

    def detect_backend(self) -> BackendState:
        """Detect backend installation state without modifying files."""
        return detect_backend_state(self.paths)

    def verify_backend(self) -> BackendVerificationResult:
        """Run placeholder-safe backend verification."""
        result = verify_backend(self.paths, self.registry)
        if self.paths.logs_dir.exists():
            write_backend_log_entry(self.paths.verify_log, "verify", result.summary, details={"status": result.status.value})
        return result

    def preview_install_plan(self) -> BackendInstallPlan:
        """Return the dry-run backend install plan without modifying files."""
        return create_backend_install_plan(self.paths, self.registry)

    def format_install_plan(self, plan: BackendInstallPlan | None = None) -> str:
        """Format the dry-run install plan for UI display."""
        return format_install_plan(plan or self.preview_install_plan())

    def install_backend(self) -> BackendOperationResult:
        """Return a planned-operation result; no installation occurs in Phase 22B."""
        return self._planned_operation("install", BackendStatus.NOT_INSTALLED)

    def repair_backend(self) -> BackendOperationResult:
        """Return a planned-operation result; no repair occurs in Phase 22B."""
        return self._planned_operation("repair", self.detect_backend().status)

    def update_backend(self) -> BackendOperationResult:
        """Return a planned-operation result; no update occurs in Phase 22B."""
        return self._planned_operation("update", self.detect_backend().status)

    def remove_backend(self) -> BackendOperationResult:
        """Return a planned-operation result; no removal occurs in Phase 22B."""
        return self._planned_operation("remove", self.detect_backend().status)

    def open_backend_folder_path(self) -> Path:
        """Return the user-local backend root path for UI integrations."""
        return self.paths.backend_root

    def get_logs(self) -> dict[str, tuple[str, ...]]:
        """Return recent backend log lines by operation."""
        return {
            "install": read_backend_log(self.paths.install_log),
            "verify": read_backend_log(self.paths.verify_log),
            "update": read_backend_log(self.paths.update_log),
            "remove": read_backend_log(self.paths.remove_log),
        }

    def get_registry(self) -> BackendRegistry:
        """Return the dependency registry, preferring persisted config when valid."""
        try:
            config = load_backend_config(self.paths.config_file)
        except Exception:  # noqa: BLE001 - bad config should not break settings UI.
            return self.registry
        return config.registry if config is not None else self.registry

    def planned_config(self):
        """Return the planned config object without writing it to disk."""
        return planned_backend_config(self.paths)

    def locate_executable(self, executable_name: str) -> Path | None:
        """Locate a backend executable by name if it exists in the managed paths."""
        candidates = [self.paths.micromamba_executable]
        bin_dir = self.paths.environment_path / ("Scripts" if self.paths.platform.value == "windows" else "bin")
        candidates.append(bin_dir / executable_name)
        if self.paths.platform.value == "windows" and not executable_name.lower().endswith(".exe"):
            candidates.append(bin_dir / f"{executable_name}.exe")
        for candidate in candidates:
            if candidate.name.lower() == executable_name.lower() or candidate.stem.lower() == executable_name.lower():
                if candidate.exists():
                    return candidate
        return None

    def run_backend_python(self, args: tuple[str, ...] = ()) -> BackendOperationResult:
        """Return a safe placeholder for future backend Python execution."""
        return BackendOperationResult(
            operation="run_backend_python",
            status=self.detect_backend().status,
            success=False,
            message="Backend Python execution is planned but disabled in Phase 22B.",
            modified_system=False,
        )

    def run_pdal_pipeline(self, pipeline_path: Path | None = None) -> BackendOperationResult:
        """Return a safe placeholder for future backend PDAL execution."""
        detail = f" Pipeline: {pipeline_path}" if pipeline_path else ""
        return BackendOperationResult(
            operation="run_pdal_pipeline",
            status=self.detect_backend().status,
            success=False,
            message=f"Backend PDAL execution is planned but disabled in Phase 22B.{detail}",
            modified_system=False,
        )

    def format_verification_report(self, result: BackendVerificationResult | None = None) -> str:
        """Format verification details for UI or logs."""
        return format_verification_result(result or self.verify_backend())

    def _planned_operation(self, operation: str, status: BackendStatus) -> BackendOperationResult:
        return BackendOperationResult(
            operation=operation,
            status=status,
            success=False,
            message="Backend installation is planned. Phase 22B provides dry-run install planning, compatibility checks, and verification scaffolding only.",
            modified_system=False,
        )
