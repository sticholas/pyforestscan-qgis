"""Placeholder-safe backend verification."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from .logging import write_backend_log_entry
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
from .process_env import build_clean_subprocess_env, conda_environment_data_env, conda_environment_path_entries, summarize_subprocess_output
from .registry import default_backend_registry
from .state import detect_backend_state


_GEOSPATIAL_STACK_PACKAGES = {
    "python",
    "gdal",
    "libgdal",
    "rasterio",
    "numpy",
    "scipy",
    "pandas",
    "shapely",
    "pyproj",
    "fiona",
    "geopandas",
    "matplotlib",
    "tqdm",
    "pdal",
    "python-pdal",
    "geos",
    "proj",
    "sqlite",
    "libsqlite",
    "libcurl",
    "curl",
    "vsicurl",
    "tiledb",
    "zstd",
    "lz4-c",
    "lz4",
}


@dataclass(frozen=True)
class CommandCheck:
    """Structured result from a verification subprocess."""

    command: tuple[str, ...]
    executable: Path
    returncode: int | None
    stdout_preview: str = ""
    stderr_preview: str = ""
    detected_version: str | None = None
    error: str = ""

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.error

    def failure_detail(self) -> str:
        if self.error:
            return self.error
        if self.stderr_preview:
            return self.stderr_preview
        if self.stdout_preview:
            return self.stdout_preview
        if self.returncode is not None:
            return f"command exited with status {self.returncode}"
        return "command did not complete"


def verify_backend(
    paths: BackendPaths,
    registry: BackendRegistry | None = None,
    timeout_seconds: int = 10,
    require_config: bool = True,
    log_path: Path | None = None,
    log_stage: str = "VERIFY",
) -> BackendVerificationResult:
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
        checks.append(_check_from_dependency(verified, paths))

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
        summary = _verification_failure_summary(checks)
    else:
        status = BackendStatus.READY
        summary = "Backend verification checks passed."

    result = BackendVerificationResult(
        status=status,
        state=state,
        checks=tuple(checks),
        registry=next_registry,
        summary=summary,
    )
    if log_path is not None:
        log_verification_checks(result, log_path, stage=log_stage)
    return result


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
        path = f" [{check.path}]" if check.path else ""
        lines.append(f"- {check.status.value.upper()} {check.name}: {check.message}{version}{path}")
        if check.command:
            lines.append(f"  Command: {_format_command(check.command)}")
        if check.executable:
            lines.append(f"  Executable: {check.executable}")
        if check.stdout_preview:
            lines.append(f"  stdout: {check.stdout_preview}")
        if check.stderr_preview:
            lines.append(f"  stderr: {check.stderr_preview}")
    return "\n".join(lines)


def log_verification_checks(result: BackendVerificationResult, log_path: Path, stage: str = "VERIFY") -> None:
    """Write one structured log entry for each backend verification check."""
    for check in result.checks:
        details = {
            "check": check.name,
            "status": check.status.value,
            "path": str(check.path) if check.path else "",
            "detected_version": check.detected_version or "",
            "command": _format_command(check.command),
            "executable": str(check.executable) if check.executable else "",
            "stdout_preview": check.stdout_preview,
            "stderr_preview": check.stderr_preview,
        }
        level = _log_level_for_check(check)
        write_backend_log_entry(log_path, "verify", check.message, level=level, stage=stage, details=details)


def _log_level_for_check(check: BackendCheckResult) -> str:
    if check.status is DependencyVerificationStatus.FAIL:
        return "ERROR"
    if check.status is DependencyVerificationStatus.WARNING:
        return "WARNING"
    warning_text = f"{check.stderr_preview}\n{check.stdout_preview}".lower()
    if "gdal_data" in warning_text or "proj_lib" in warning_text or "proj_data" in warning_text:
        return "WARNING"
    return "INFO"


def failed_check_summary(result: BackendVerificationResult, limit: int = 8) -> str:
    """Return actionable failed-check lines for install result messages."""
    checks = tuple(getattr(result, "checks", ()))
    failed = [check for check in checks if check.status is DependencyVerificationStatus.FAIL]
    if not failed:
        return getattr(result, "summary", "Backend verification failed.")
    lines = ["Failed verification checks:"]
    for check in failed[:limit]:
        detail = check.stderr_preview or check.stdout_preview
        suffix = f" ({detail})" if detail and detail not in check.message else ""
        lines.append(f"- {check.name}: {check.message}{suffix}")
    if len(failed) > limit:
        lines.append(f"- ... {len(failed) - limit} more failed check(s)")
    return "\n".join(lines)


def python_import_command(python_executable: Path, import_name: str) -> tuple[str, ...]:
    """Return the backend Python import/version check command."""
    if import_name == "rasterio":
        code = (
            "import rasterio; "
            "print('rasterio=' + str(getattr(rasterio, '__version__', 'UNKNOWN'))); "
            "print('rasterio_gdal=' + str(getattr(rasterio, '__gdal_version__', 'UNKNOWN'))); "
            "from rasterio.io import MemoryFile; "
            "m=MemoryFile(); m.close(); "
            "print('rasterio_memoryfile=ok')"
        )
        return (str(python_executable), "-c", code)
    if import_name == "pyforestscan":
        modules = (
            "pyforestscan",
            "pyforestscan.calculate",
            "pyforestscan.filters",
            "pyforestscan.handlers",
            "pyforestscan.process",
            "pyforestscan.visualize",
        )
        module_literal = repr(modules)
        code = (
            "import importlib; "
            f"mods={module_literal}; "
            "loaded=[]; "
            "[loaded.append(importlib.import_module(name).__name__) for name in mods]; "
            "root=importlib.import_module('pyforestscan'); "
            "print('pyforestscan=' + str(getattr(root, '__version__', 'UNKNOWN'))); "
            "print('pyforestscan_modules=' + ','.join(loaded))"
        )
        return (str(python_executable), "-c", code)
    code = (
        "import importlib; "
        f"m=importlib.import_module({import_name!r}); "
        "print(getattr(m, '__version__', 'UNKNOWN'))"
    )
    return (str(python_executable), "-c", code)


def _path_check(name: str, path: Path, required: bool) -> BackendCheckResult:
    if path.exists():
        return BackendCheckResult(name=name, status=DependencyVerificationStatus.PASS, message="Found", path=path)
    status = DependencyVerificationStatus.FAIL if required else DependencyVerificationStatus.WARNING
    return BackendCheckResult(name=name, status=status, message="Missing", path=path)


def _verify_dependency(dependency: BackendDependency, paths: BackendPaths, timeout_seconds: int) -> BackendDependency:
    executable_path = _dependency_path(dependency, paths)
    command_checks: list[CommandCheck] = []
    messages: list[str] = []
    detected_version: str | None = None
    executable_missing = False

    if dependency.executable_name:
        if executable_path and executable_path.exists():
            if dependency.verification_command:
                version_check = _run_version_command(executable_path, dependency.verification_command, timeout_seconds, paths)
                command_checks.append(version_check)
                if version_check.passed:
                    detected_version = version_check.detected_version or detected_version
                    messages.append(f"{dependency.executable_name} command verified")
                else:
                    messages.append(f"{dependency.executable_name} command failed: {version_check.failure_detail()}")
            else:
                messages.append(f"{dependency.executable_name} executable found")
        else:
            executable_missing = True
            searched = ", ".join(str(path) for path in _dependency_candidate_paths(dependency, paths))
            messages.append(f"{dependency.executable_name} executable not found. Searched: {searched}")

    if dependency.python_import_name:
        if not paths.python_executable.exists():
            messages.append(f"Backend Python is not available for import {dependency.python_import_name}.")
            return _dependency_with_diagnostics(
                dependency,
                install_status=DependencyInstallStatus.MISSING,
                verification_status=DependencyVerificationStatus.FAIL if dependency.required else DependencyVerificationStatus.WARNING,
                detected_version=detected_version,
                notes=" ".join(messages),
                command_checks=tuple(command_checks),
                path=executable_path,
            )
        import_check = _run_python_import(paths.python_executable, dependency.python_import_name, timeout_seconds, paths)
        command_checks.append(import_check)
        if import_check.passed:
            detected_version = import_check.detected_version or detected_version
            messages.append(f"import {dependency.python_import_name} verified")
        else:
            messages.append(f"import {dependency.python_import_name} failed: {import_check.failure_detail()}")
        if dependency.name == "rasterio":
            stack_check = conda_stack_summary(paths, timeout_seconds=timeout_seconds)
            if stack_check.stdout_preview:
                messages.append(f"Conda geospatial package summary: {stack_check.stdout_preview}")
            elif not stack_check.passed:
                messages.append(f"Conda geospatial package summary unavailable: {stack_check.failure_detail()}")

    failed_commands = [check for check in command_checks if not check.passed]
    if executable_missing or failed_commands:
        status = DependencyVerificationStatus.FAIL if dependency.required else DependencyVerificationStatus.WARNING
        install_status = DependencyInstallStatus.MISSING if executable_missing else DependencyInstallStatus.PRESENT
    elif command_checks or (dependency.executable_name and executable_path and executable_path.exists()):
        status = DependencyVerificationStatus.PASS
        install_status = DependencyInstallStatus.PRESENT
    else:
        status = DependencyVerificationStatus.FAIL if dependency.required else DependencyVerificationStatus.WARNING
        install_status = DependencyInstallStatus.MISSING
        messages.append("No executable or import verification target is available.")

    return _dependency_with_diagnostics(
        dependency,
        install_status=install_status,
        verification_status=status,
        detected_version=detected_version,
        notes="; ".join(messages),
        command_checks=tuple(command_checks),
        path=executable_path,
    )


def _dependency_with_diagnostics(
    dependency: BackendDependency,
    install_status: DependencyInstallStatus,
    verification_status: DependencyVerificationStatus,
    detected_version: str | None,
    notes: str,
    command_checks: tuple[CommandCheck, ...],
    path: Path | None,
) -> BackendDependency:
    next_dependency = replace(
        dependency,
        install_status=install_status,
        verification_status=verification_status,
        detected_version=detected_version,
        notes=notes or dependency.notes,
    )
    object.__setattr__(next_dependency, "_command_checks", command_checks)
    object.__setattr__(next_dependency, "_verification_path", path)
    return next_dependency


def _check_from_dependency(dependency: BackendDependency, paths: BackendPaths) -> BackendCheckResult:
    command_checks: tuple[CommandCheck, ...] = getattr(dependency, "_command_checks", ())
    failed = next((check for check in command_checks if not check.passed), None)
    first = failed or (command_checks[-1] if command_checks else None)
    path = getattr(dependency, "_verification_path", None) or _dependency_path(dependency, paths)
    return BackendCheckResult(
        name=dependency.display_name,
        status=dependency.verification_status,
        message=_dependency_message(dependency),
        detected_version=dependency.detected_version,
        path=path,
        command=first.command if first else (),
        executable=first.executable if first else path,
        stdout_preview=first.stdout_preview if first else "",
        stderr_preview=first.stderr_preview if first else "",
    )


def _dependency_path(dependency: BackendDependency, paths: BackendPaths) -> Path | None:
    candidates = _dependency_candidate_paths(dependency, paths)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _dependency_candidate_paths(dependency: BackendDependency, paths: BackendPaths) -> tuple[Path, ...]:
    if not dependency.executable_name:
        return ()
    name = dependency.executable_name
    if dependency.name == "micromamba":
        return (paths.micromamba_executable,)
    if dependency.name == "python":
        return (paths.python_executable,)
    names = (name,)
    if paths.platform.value == "windows" and not name.lower().endswith(".exe"):
        names = (f"{name}.exe", name)
    search_dirs = _backend_executable_search_dirs(paths)
    return tuple(directory / candidate_name for directory in search_dirs for candidate_name in names)


def _backend_executable_search_dirs(paths: BackendPaths) -> tuple[Path, ...]:
    if paths.platform.value == "windows":
        return (
            paths.environment_path / "Scripts",
            paths.environment_path / "Library" / "bin",
            paths.environment_path / "bin",
            paths.environment_path,
        )
    return (
        paths.environment_path / "bin",
        paths.environment_path,
    )


def _dependency_message(dependency: BackendDependency) -> str:
    if dependency.notes and ("failed:" in dependency.notes or "not found" in dependency.notes or "not available" in dependency.notes):
        return dependency.notes
    if dependency.verification_status is DependencyVerificationStatus.PASS:
        return dependency.notes or "Verified"
    if dependency.verification_status is DependencyVerificationStatus.WARNING:
        return dependency.notes or "Detected with warnings or reserved as an optional future module"
    return dependency.notes or "Missing or not verifiable in the managed backend"


def _run_version_command(executable: Path, args: tuple[str, ...], timeout_seconds: int, paths: BackendPaths) -> CommandCheck:
    command = (str(executable), *args)
    return _run_command(command, executable, timeout_seconds, paths)


def _run_python_import(python_executable: Path, import_name: str, timeout_seconds: int, paths: BackendPaths) -> CommandCheck:
    command = python_import_command(python_executable, import_name)
    return _run_command(command, python_executable, timeout_seconds, paths)


def _run_command(command: tuple[str, ...], executable: Path, timeout_seconds: int, paths: BackendPaths) -> CommandCheck:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=build_clean_subprocess_env(prepend_paths=_verification_path_entries(paths, executable), extra_env=conda_environment_data_env(paths.environment_path, paths.platform.value)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandCheck(command=command, executable=executable, returncode=None, error=str(exc))
    stdout_preview = summarize_subprocess_output(completed.stdout, "")
    stderr_preview = summarize_subprocess_output(completed.stderr, "")
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    detected_version = output[0] if completed.returncode == 0 and output else None
    return CommandCheck(
        command=command,
        executable=executable,
        returncode=completed.returncode,
        stdout_preview=stdout_preview,
        stderr_preview=stderr_preview,
        detected_version=detected_version,
    )


def conda_stack_summary(paths: BackendPaths, timeout_seconds: int = 10) -> CommandCheck:
    """Return filtered conda package/build diagnostics for the geospatial stack."""
    executable = paths.micromamba_executable
    command = (str(executable), "list", "-p", str(paths.environment_path))
    if not executable.exists():
        return CommandCheck(command=command, executable=executable, returncode=None, error="Micromamba executable is not available for conda package diagnostics.")
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=build_clean_subprocess_env(prepend_paths=_verification_path_entries(paths, executable), extra_env=conda_environment_data_env(paths.environment_path, paths.platform.value)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandCheck(command=command, executable=executable, returncode=None, error=str(exc))
    filtered = _filter_conda_stack_lines(completed.stdout)
    stdout_preview = filtered or summarize_subprocess_output(completed.stdout, "")
    stderr_preview = summarize_subprocess_output(completed.stderr, "")
    first = stdout_preview.splitlines()[0] if stdout_preview else None
    return CommandCheck(
        command=command,
        executable=executable,
        returncode=completed.returncode,
        stdout_preview=stdout_preview,
        stderr_preview=stderr_preview,
        detected_version=first,
    )


def _filter_conda_stack_lines(output: str) -> str:
    lines: list[str] = []
    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        package = stripped.split()[0].lower()
        if package in _GEOSPATIAL_STACK_PACKAGES:
            lines.append(stripped)
    return "\n".join(lines)


def _verification_path_entries(paths: BackendPaths, executable: Path) -> tuple[Path, ...]:
    entries = list(conda_environment_path_entries(paths.environment_path, paths.platform.value))
    if executable.parent not in entries:
        entries.append(executable.parent)
    return tuple(entries)


def _verification_failure_summary(checks: list[BackendCheckResult]) -> str:
    failed = [check for check in checks if check.status is DependencyVerificationStatus.FAIL]
    if not failed:
        return "Backend files are incomplete or required dependencies are missing."
    lines = ["Backend verification failed:"]
    for check in failed[:8]:
        lines.append(f"- {check.name}: {check.message}")
    if len(failed) > 8:
        lines.append(f"- ... {len(failed) - 8} more failed check(s)")
    return "\n".join(lines)


def _format_command(command: tuple[str, ...]) -> str:
    return " ".join(command) if command else ""
