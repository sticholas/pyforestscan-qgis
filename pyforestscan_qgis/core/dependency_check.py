"""Runtime environment validation for PyForestScan QGIS.

This module is intentionally plain Python so it can be tested outside QGIS. It
checks the active interpreter and dependency importability, then renders a
stable diagnostic report for the QGIS Processing Environment Check algorithm.
"""

from __future__ import annotations

import importlib
import platform
import sys
from dataclasses import dataclass
from enum import Enum
from importlib import metadata
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable


class CheckStatus(str, Enum):
    """User-facing status for one environment check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class ReadinessStatus(str, Enum):
    """Overall readiness classification for the active environment."""

    READY = "READY"
    PARTIALLY_READY = "PARTIALLY READY"
    NOT_READY = "NOT READY"


@dataclass(frozen=True)
class EnvironmentCheckResult:
    """Structured result for one diagnostic check."""

    name: str
    status: CheckStatus
    message: str
    version: str | None = None
    guidance: str = ""


@dataclass(frozen=True)
class EnvironmentReport:
    """Structured environment validation report."""

    checks: tuple[EnvironmentCheckResult, ...]
    readiness: ReadinessStatus
    summary: str


ImportModule = Callable[[str], ModuleType]
VersionLookup = Callable[[str], str]
PBMBackendCheck = Callable[[], EnvironmentCheckResult]
ExecutionBackendCheck = Callable[[], EnvironmentCheckResult]


INSTALLATION_GUIDANCE = (
    "ZIP installation only installs the QGIS plugin. Scientific processing also "
    "requires PyForestScan, PDAL, GDAL, rasterio, and numpy in the active QGIS "
    "Python environment unless a workflow explicitly supports the managed PBM "
    "backend. Windows internal beta builds can install PBM into the user-local "
    "PyForestScan folder without changing QGIS or system Python. Do not use "
    "system Python unless it is the Python used by QGIS. See "
    "docs/INSTALLATION_STRATEGY.md and docs/releases/CLEAN_MACHINE_SMOKE_TEST.md."
)


def collect_environment_report(
    plugin_path: Path | str | None = None,
    import_module: ImportModule | None = None,
    version_lookup: VersionLookup | None = None,
    include_pbm_backend: bool = True,
    pbm_backend_check: PBMBackendCheck | None = None,
    execution_backend_check: ExecutionBackendCheck | None = None,
) -> EnvironmentReport:
    """Collect structured diagnostics for the active runtime environment.

    Args:
        plugin_path: Optional plugin package path to include in the report.
        import_module: Optional import function used by tests.
        version_lookup: Optional package metadata lookup used by tests.
        include_pbm_backend: Include managed-backend readiness diagnostics.
        pbm_backend_check: Optional PBM check override used by tests.
        execution_backend_check: Optional execution backend check override used by tests.

    Returns:
        EnvironmentReport containing individual checks and final readiness.
    """
    importer = import_module or importlib.import_module
    lookup = version_lookup or metadata.version

    checks: list[EnvironmentCheckResult] = [
        _python_executable_check(),
        _python_version_check(),
        _platform_check(),
        _qgis_version_check(importer),
        _plugin_path_check(plugin_path),
        _dependency_check(
            display_name="pyforestscan",
            import_name="pyforestscan",
            package_name="pyforestscan",
            importer=importer,
            version_lookup=lookup,
            required=True,
            guidance=(
                "PyForestScan is missing from QGIS Python. ZIP install is still usable "
                "for opening Mission Control and diagnostics, but processing cannot run "
                "until PyForestScan is available in QGIS Python or PBM backend execution is selected for this product."
            ),
        ),
        _dependency_check(
            display_name="pdal",
            import_name="pdal",
            package_name="pdal",
            importer=importer,
            version_lookup=lookup,
            required=True,
            guidance=(
                "PDAL Python bindings are missing from QGIS Python. Install PDAL and "
                "python-pdal for the same QGIS environment; mismatched system Python "
                "installs will not fix QGIS Processing."
            ),
        ),
        _dependency_check(
            display_name="osgeo.gdal",
            import_name="osgeo.gdal",
            package_name="GDAL",
            importer=importer,
            version_lookup=lookup,
            required=True,
            version_getter=_gdal_version,
            guidance=(
                "GDAL bindings are not importable from QGIS Python. Confirm the QGIS "
                "installation is healthy before installing extra packages; GDAL usually "
                "comes from QGIS/OSGeo4W rather than system Python."
            ),
        ),
        _dependency_check(
            display_name="rasterio",
            import_name="rasterio",
            package_name="rasterio",
            importer=importer,
            version_lookup=lookup,
            required=True,
            guidance=(
                "rasterio is missing from QGIS Python. Install a rasterio build that is "
                "compatible with the GDAL version used by QGIS."
            ),
        ),
        _dependency_check(
            display_name="numpy",
            import_name="numpy",
            package_name="numpy",
            importer=importer,
            version_lookup=lookup,
            required=True,
            guidance="numpy is missing from QGIS Python. Install numpy into the exact interpreter used by QGIS.",
        ),
    ]

    if include_pbm_backend:
        checks.append((pbm_backend_check or _pbm_backend_status_check)())
        checks.append((execution_backend_check or _selected_execution_backend_check)())

    return build_environment_report(checks)


def build_environment_report(
    checks: Iterable[EnvironmentCheckResult],
) -> EnvironmentReport:
    """Build the final report and readiness value from individual checks."""
    check_tuple = tuple(checks)
    if any(check.status is CheckStatus.FAIL for check in check_tuple):
        readiness = ReadinessStatus.NOT_READY
        summary = "One or more required dependencies are missing."
    elif any(check.status is CheckStatus.WARNING for check in check_tuple):
        readiness = ReadinessStatus.PARTIALLY_READY
        summary = "Required dependencies imported, but warnings need review."
    else:
        readiness = ReadinessStatus.READY
        summary = "Required environment checks passed."

    return EnvironmentReport(
        checks=check_tuple,
        readiness=readiness,
        summary=summary,
    )


def format_environment_report(report: EnvironmentReport) -> str:
    """Render a user-facing diagnostic report."""
    lines = [
        "PyForestScan QGIS Environment Check",
        "===================================",
        "",
    ]

    for check in report.checks:
        version = f" (version: {check.version})" if check.version else ""
        lines.append(f"[{check.status.value}] {check.name}: {check.message}{version}")
        if check.guidance:
            lines.append(f"    Guidance: {check.guidance}")

    lines.extend(
        [
            "",
            f"Final summary: {report.readiness.value}",
            report.summary,
            "",
            "Installation guidance:",
            INSTALLATION_GUIDANCE,
        ]
    )
    return "\n".join(lines)



def _selected_execution_backend_check() -> EnvironmentCheckResult:
    """Report which execution backend the adapter would currently select."""
    try:
        from .adapter import PyForestScanAdapter

        backend = PyForestScanAdapter().selected_execution_backend()
    except Exception as exc:  # noqa: BLE001 - diagnostics must never crash.
        return EnvironmentCheckResult(
            name="Selected execution backend",
            status=CheckStatus.WARNING,
            message=f"Could not determine selected execution backend: {exc}",
        )
    if backend == "pbm_backend":
        return EnvironmentCheckResult(
            name="Selected execution backend",
            status=CheckStatus.PASS,
            message="PyForestScan Backend Manager will be preferred for routed processing products.",
            guidance="QGIS will orchestrate jobs and load outputs; heavy routed products run in PBM backend Python.",
        )
    return EnvironmentCheckResult(
        name="Selected execution backend",
        status=CheckStatus.WARNING,
        message="QGIS Python will be used for processing unless PBM backend becomes READY.",
        guidance="Install or repair PBM backend to avoid requiring PyForestScan/PDAL in QGIS Python for routed products.",
    )


def _python_executable_check() -> EnvironmentCheckResult:
    return EnvironmentCheckResult(
        name="QGIS Python executable path",
        status=CheckStatus.PASS,
        message=sys.executable or "Unknown executable",
    )


def _python_version_check() -> EnvironmentCheckResult:
    return EnvironmentCheckResult(
        name="Python version",
        status=CheckStatus.PASS,
        message=platform.python_version(),
    )


def _platform_check() -> EnvironmentCheckResult:
    return EnvironmentCheckResult(
        name="Platform / operating system",
        status=CheckStatus.PASS,
        message=platform.platform(),
    )


def _plugin_path_check(plugin_path: Path | str | None) -> EnvironmentCheckResult:
    if plugin_path is None:
        path = Path(__file__).resolve().parents[1]
    else:
        path = Path(plugin_path).resolve()

    return EnvironmentCheckResult(
        name="Plugin path",
        status=CheckStatus.PASS,
        message=str(path),
    )


def _qgis_version_check(importer: ImportModule) -> EnvironmentCheckResult:
    try:
        qgis_core = importer("qgis.core")
    except Exception as exc:  # noqa: BLE001 - diagnostics must never crash.
        return EnvironmentCheckResult(
            name="QGIS version",
            status=CheckStatus.WARNING,
            message="QGIS Python API is not importable from this interpreter.",
            guidance=(
                "Run this Processing algorithm inside QGIS to verify the QGIS "
                f"runtime. Import error: {exc}"
            ),
        )

    qgis_class = getattr(qgis_core, "Qgis", None)
    version = getattr(qgis_class, "QGIS_VERSION", None)
    if version:
        return EnvironmentCheckResult(
            name="QGIS version",
            status=CheckStatus.PASS,
            message="QGIS Python API is available.",
            version=str(version),
        )

    return EnvironmentCheckResult(
        name="QGIS version",
        status=CheckStatus.WARNING,
        message="QGIS Python API imported, but version could not be determined.",
    )


def _dependency_check(
    display_name: str,
    import_name: str,
    package_name: str,
    importer: ImportModule,
    version_lookup: VersionLookup,
    required: bool,
    guidance: str,
    version_getter: Callable[[ModuleType], str | None] | None = None,
) -> EnvironmentCheckResult:
    try:
        module = importer(import_name)
    except Exception as exc:  # noqa: BLE001 - diagnostics must never crash.
        status = CheckStatus.FAIL if required else CheckStatus.WARNING
        return EnvironmentCheckResult(
            name=display_name,
            status=status,
            message=f"Could not import {import_name}: {exc}",
            guidance=guidance,
        )

    version = _module_version(module, package_name, version_lookup, version_getter)
    if version:
        return EnvironmentCheckResult(
            name=display_name,
            status=CheckStatus.PASS,
            message=f"Imported {import_name} successfully.",
            version=version,
        )

    return EnvironmentCheckResult(
        name=display_name,
        status=CheckStatus.WARNING,
        message=f"Imported {import_name}, but version could not be determined.",
        guidance=(
            "Verify compatibility manually before running production workflows."
        ),
    )


def _module_version(
    module: ModuleType,
    package_name: str,
    version_lookup: VersionLookup,
    version_getter: Callable[[ModuleType], str | None] | None,
) -> str | None:
    if version_getter is not None:
        version = version_getter(module)
        if version:
            return version

    module_version = getattr(module, "__version__", None)
    if module_version:
        return str(module_version)

    try:
        return version_lookup(package_name)
    except Exception:  # noqa: BLE001 - missing package metadata is diagnostic only.
        return None


def _gdal_version(module: ModuleType) -> str | None:
    version_info = getattr(module, "VersionInfo", None)
    if callable(version_info):
        try:
            version = version_info("--version")
        except TypeError:
            version = version_info()
        if version:
            return str(version)
    return None
