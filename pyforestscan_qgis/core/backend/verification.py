"""Placeholder-safe backend verification."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

from .models import (
    BackendCheckResult,
    BackendDependency,
    BackendRegistry,
    BackendStatus,
    BackendVerificationResult,
    DependencyInstallStatus,
    DependencyVerificationStatus,
)
from .paths import BackendPaths
from .process_env import build_clean_subprocess_env
from .registry import default_backend_registry
from .state import detect_backend_state


def verify_backend(paths: BackendPaths, registry: BackendRegistry | None = None, timeout_seconds: int = 10, require_config: bool = True) -> BackendVerificationResult:
    """Verify the backend without downloading, installing, or modifying QGIS."""
    registry_value = registry or default_backend_registry()
    state = detect_backend_state(paths)
    checks: list[BackendCheckResult] = [
        _path_check("Backend root", paths.backend_root, required=True),
    ]
    if require_config:
        checks.append(_path_check("Backend config", paths.config_file, required=True))
    checks.extend(
        [
            _path_check("Micromamba executable", paths.micromamba_executable, required=True),
            _path_check("Backend environment", paths.environment_path, required=True),
            _path_check("Backend Python", paths.python_executable, required=True),
        ]
    )

    dependencies: list[BackendDependency] = []
    for dependency in registry_value.dependencies:
        verified = _verify_dependency(dependency, paths, timeout_seconds=timeout_seconds)
        dependencies.append(verified)
        checks.append(
            BackendCheckResult(
                name=dependency.display_name,
                status=verified.verification_status,
                message=_dependency_message(verified),
                detected_version=verified.detected_version,
                path=_dependency_path(verified, paths),
            )
        )

    next_registry = BackendRegistry(dependencies=tuple(dependencies), registry_version=registry_value.registry_version)
    failures = [check for check in checks if check.status is DependencyVerificationStatus.FAIL]
    required_failures = [
        dependency for dependency in dependencies if dependency.required and dependency.verification_status is DependencyVerificationStatus.FAIL
    ]
    if not paths.backend_root.exists():
        status = BackendStatus.NOT_INSTALLED
        summary = "Backend is not installed. Normal user installation is disabled; Phase 22C installer mechanics require the developer guard."
    elif required_failures or failures:
        status = BackendStatus.REPAIR_REQUIRED
        summary = "Backend files are incomplete or required dependencies are missing."
    else:
        status = BackendStatus.READY
        summary = "Backend verification checks passed."

    return BackendVerificationResult(
        status=status,
        state=state,
        checks=tuple(checks),
        registry=next_registry,
        summary=summary,
    )


def format_verification_result(result: BackendVerificationResult) -> str:
    """Render a concise user-facing backend verification report."""
    lines = [
        "PyForestScan Backend Manager Verification",
        "=========================================",
        f"Status: {result.status.value}",
        f"Backend root: {result.state.backend_root}",
        result.summary,
        "",
        "Checks:",
    ]
    for check in result.checks:
        version = f" ({check.detected_version})" if check.detected_version else ""
        lines.append(f"- {check.status.value.upper()} {check.name}: {check.message}{version}")
    return "\n".join(lines)


def _path_check(name: str, path: Path, required: bool) -> BackendCheckResult:
    if path.exists():
        return BackendCheckResult(name=name, status=DependencyVerificationStatus.PASS, message="Found", path=path)
    status = DependencyVerificationStatus.FAIL if required else DependencyVerificationStatus.WARNING
    return BackendCheckResult(name=name, status=status, message="Missing", path=path)


def _verify_dependency(dependency: BackendDependency, paths: BackendPaths, timeout_seconds: int) -> BackendDependency:
    executable_path = _dependency_path(dependency, paths)
    if dependency.executable_name and executable_path and executable_path.exists() and dependency.verification_command:
        version = _run_version_command(executable_path, dependency.verification_command, timeout_seconds)
        status = DependencyVerificationStatus.PASS if version else DependencyVerificationStatus.WARNING
        return replace(
            dependency,
            install_status=DependencyInstallStatus.PRESENT,
            verification_status=status,
            detected_version=version,
        )
    if dependency.python_import_name:
        if not paths.python_executable.exists():
            return replace(
                dependency,
                install_status=DependencyInstallStatus.MISSING,
                verification_status=DependencyVerificationStatus.FAIL if dependency.required else DependencyVerificationStatus.WARNING,
                notes=(dependency.notes + " Backend Python is not available for import verification.").strip(),
            )
        version = _run_python_import(paths.python_executable, dependency.python_import_name, timeout_seconds)
        status = DependencyVerificationStatus.PASS if version else DependencyVerificationStatus.FAIL if dependency.required else DependencyVerificationStatus.WARNING
        return replace(
            dependency,
            install_status=DependencyInstallStatus.PRESENT if version else DependencyInstallStatus.MISSING,
            verification_status=status,
            detected_version=version,
        )
    if dependency.executable_name and executable_path and executable_path.exists():
        return replace(dependency, install_status=DependencyInstallStatus.PRESENT, verification_status=DependencyVerificationStatus.PASS)
    return replace(
        dependency,
        install_status=DependencyInstallStatus.MISSING,
        verification_status=DependencyVerificationStatus.FAIL if dependency.required else DependencyVerificationStatus.WARNING,
    )


def _dependency_path(dependency: BackendDependency, paths: BackendPaths) -> Path | None:
    if not dependency.executable_name:
        return None
    name = dependency.executable_name
    if dependency.name == "micromamba":
        return paths.micromamba_executable
    if dependency.name == "python":
        return paths.python_executable
    if paths.platform.value == "windows" and not name.lower().endswith(".exe"):
        name = f"{name}.exe"
    bin_dir = paths.environment_path / ("Scripts" if paths.platform.value == "windows" else "bin")
    return bin_dir / name


def _dependency_message(dependency: BackendDependency) -> str:
    if dependency.verification_status is DependencyVerificationStatus.PASS:
        return "Verified"
    if dependency.verification_status is DependencyVerificationStatus.WARNING:
        return "Detected with warnings or reserved as an optional future module"
    return "Missing or not verifiable in the managed backend"


def _run_version_command(executable: Path, args: tuple[str, ...], timeout_seconds: int) -> str | None:
    try:
        completed = subprocess.run(
            [str(executable), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=build_clean_subprocess_env(prepend_paths=(executable.parent,)),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    return output[0] if output else None


def _run_python_import(python_executable: Path, import_name: str, timeout_seconds: int) -> str | None:
    code = (
        "import importlib, sys; "
        f"m=importlib.import_module({import_name!r}); "
        "print(getattr(m, '__version__', 'UNKNOWN'))"
    )
    try:
        completed = subprocess.run(
            [str(python_executable), "-c", code],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=build_clean_subprocess_env(prepend_paths=(python_executable.parent,)),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or "UNKNOWN").strip().splitlines()[0]
