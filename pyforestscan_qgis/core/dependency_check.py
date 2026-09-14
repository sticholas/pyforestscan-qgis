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
    """Overall readiness classification for processing capability."""

    READY = "READY"
    READY_WITH_QGIS_PYTHON = "READY WITH QGIS PYTHON"
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
    "ZIP installation only installs the QGIS plugin. PBM is the intended "
    "execution backend for routed products when it is READY. QGIS Python "
    "scientific packages are an optional fallback environment except for "
    "QGIS-Python-only tools such as Height Above Ground point-cloud export and "
    "Preprocess Point Cloud. Windows internal beta builds install PBM into the "
    "user-local PyForestScan folder without changing QGIS or system Python."
)


QGIS_RUNTIME_CHECKS = {
    "QGIS Python executable path",
    "Python version",
    "Platform / operating system",
    "QGIS version",
    "Plugin path",
}
QGIS_FALLBACK_CHECKS = {"pyforestscan", "pdal", "osgeo.gdal", "rasterio", "numpy"}
QGIS_SCIENTIFIC_CHECKS = QGIS_FALLBACK_CHECKS
PBM_CHECKS = {"PBM managed backend"}
EXECUTION_CHECKS = {"Active execution backend", "Selected execution backend", "No-manual-setup scope"}
PBM_ROUTED_PRODUCTS = (
    "Dataset Explorer local inspection",
    "CHM",
    "Canopy Cover",
    "PAD",
    "PAI",
    "FHD",
    "Rumple",
    "DTM",
    "Point Density",
    "Voxel Statistic",
)
QGIS_PYTHON_ONLY_PRODUCTS = (
    "Height Above Ground point-cloud export",
    "Preprocess Point Cloud",
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
                "PyForestScan is missing from QGIS Python. PBM-routed products can "
                "run when PBM backend is READY; QGIS-Python-only tools still require "
                "PyForestScan in the active QGIS Python environment."
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
                "PDAL Python bindings are missing from QGIS Python. PBM-routed "
                "products can use the managed backend when READY. Install PDAL and "
                "python-pdal into QGIS Python only for QGIS-Python-only tools."
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
        selected_backend = (execution_backend_check or _selected_execution_backend_check)()
        checks.append(selected_backend)
        checks.append(_no_manual_setup_scope_check(selected_backend))

    return build_environment_report(checks)


def build_environment_report(
    checks: Iterable[EnvironmentCheckResult],
) -> EnvironmentReport:
    """Build the final report and readiness value from individual checks."""
    check_tuple = tuple(checks)
    by_name = {check.name: check for check in check_tuple}
    has_full_environment_sections = QGIS_FALLBACK_CHECKS.issubset(by_name) and "PBM managed backend" in by_name
    if has_full_environment_sections:
        pbm_check = by_name["PBM managed backend"]
        pbm_ready = _pbm_check_is_ready(pbm_check)
        check_tuple = _with_optional_qgis_fallback_checks(check_tuple, pbm_ready)
        by_name = {check.name: check for check in check_tuple}
        qgis_fallback_ready = all(by_name[name].status is not CheckStatus.FAIL for name in QGIS_FALLBACK_CHECKS)
        if pbm_ready:
            readiness = ReadinessStatus.READY
            summary = "PBM backend is READY. Execution Backend: PBM Backend. Routed processing can run without QGIS Python PyForestScan/PDAL."
        elif qgis_fallback_ready:
            readiness = ReadinessStatus.READY_WITH_QGIS_PYTHON
            summary = "QGIS Python fallback environment is ready. PBM backend is optional or not installed."
        else:
            readiness = ReadinessStatus.NOT_READY
            summary = "Neither PBM backend nor QGIS Python fallback environment is ready for processing."
    elif any(check.status is CheckStatus.FAIL for check in check_tuple):
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
        f"Overall Environment Status: {report.readiness.value}",
        "",
    ]
    sections = (
        ("QGIS / Plugin Runtime", QGIS_RUNTIME_CHECKS),
        ("PBM Managed Backend", PBM_CHECKS),
        ("Execution Readiness", EXECUTION_CHECKS),
        ("QGIS Python fallback environment", QGIS_FALLBACK_CHECKS),
    )
    rendered: set[int] = set()
    for title, names in sections:
        section_checks = [check for check in report.checks if check.name in names]
        if not section_checks:
            continue
        lines.extend([title, "-" * len(title)])
        for check in section_checks:
            rendered.add(id(check))
            _append_check_lines(lines, check)
        if title == "PBM Managed Backend" and report.readiness is ReadinessStatus.READY:
            lines.append("PBM Backend: READY")
            lines.append("Routed products available: " + ", ".join(PBM_ROUTED_PRODUCTS) + ".")
        if title == "Execution Readiness":
            lines.append("PBM-routed products: " + ", ".join(PBM_ROUTED_PRODUCTS) + ".")
            lines.append("QGIS-Python-only remaining: " + ", ".join(QGIS_PYTHON_ONLY_PRODUCTS) + ".")
        lines.append("")

    remaining = [check for check in report.checks if id(check) not in rendered]
    if remaining:
        lines.extend(["Additional Checks", "-----------------"])
        for check in remaining:
            _append_check_lines(lines, check)
        lines.append("")

    lines.extend(
        [
            f"Final summary: {report.readiness.value}",
            report.summary,
            "",
            "Recommended Next Step:",
            _recommended_next_step(report),
            "",
            "Installation guidance:",
            INSTALLATION_GUIDANCE,
        ]
    )
    return "\n".join(lines)


def _append_check_lines(lines: list[str], check: EnvironmentCheckResult) -> None:
    version = f" (version: {check.version})" if check.version else ""
    lines.append(f"[{check.status.value}] {check.name}: {check.message}{version}")
    if check.guidance:
        lines.append(f"    Guidance: {check.guidance}")


def _pbm_check_is_ready(check: EnvironmentCheckResult) -> bool:
    return check.status is CheckStatus.PASS and ("ready" in check.message.lower() or "verified" in check.message.lower())


def _with_optional_qgis_fallback_checks(checks: tuple[EnvironmentCheckResult, ...], pbm_ready: bool) -> tuple[EnvironmentCheckResult, ...]:
    if not pbm_ready:
        return checks
    updated: list[EnvironmentCheckResult] = []
    for check in checks:
        if check.name in QGIS_FALLBACK_CHECKS and check.status is CheckStatus.FAIL:
            updated.append(
                EnvironmentCheckResult(
                    name=check.name,
                    status=CheckStatus.WARNING,
                    message="Not installed — optional when PBM backend is READY.",
                    version=check.version,
                    guidance="Install into QGIS Python only if you choose QGIS-Python-only tools or want a manual fallback.",
                )
            )
        else:
            updated.append(check)
    return tuple(updated)


def _recommended_next_step(report: EnvironmentReport) -> str:
    if report.readiness is ReadinessStatus.READY_WITH_QGIS_PYTHON:
        return "Processing can run through QGIS Python. PBM backend installation is optional for no-manual-setup routed workflows."
    if report.readiness is ReadinessStatus.READY:
        return "Run PBM-routed products normally. Install QGIS Python scientific packages only if you need Height Above Ground export, Preprocess Point Cloud, or a manual fallback."
    if report.readiness is ReadinessStatus.NOT_READY:
        return "Install or repair PBM backend, or install matching scientific packages into the active QGIS Python environment."
    return "Review warnings, then choose PBM backend or QGIS Python based on the workflow you plan to run."



def _selected_execution_backend_check() -> EnvironmentCheckResult:
    """Report which execution backend the adapter would currently select."""
    try:
        from .adapter import PyForestScanAdapter

        backend = PyForestScanAdapter().selected_execution_backend()
    except Exception as exc:  # noqa: BLE001 - diagnostics must never crash.
        return EnvironmentCheckResult(
            name="Active execution backend",
            status=CheckStatus.WARNING,
            message=f"Could not determine selected execution backend: {exc}",
        )
    if backend == "pbm_backend":
        return EnvironmentCheckResult(
            name="Active execution backend",
            status=CheckStatus.PASS,
            message="PyForestScan Backend Manager will be preferred for routed processing products.",
            guidance="QGIS will orchestrate jobs and load outputs; heavy routed products run in PBM backend Python.",
        )
    return EnvironmentCheckResult(
        name="Active execution backend",
        status=CheckStatus.WARNING,
        message="QGIS Python will be used for processing unless PBM backend becomes READY.",
        guidance="Install or repair PBM backend to avoid requiring PyForestScan/PDAL in QGIS Python for routed products.",
    )



def _pbm_backend_status_check() -> EnvironmentCheckResult:
    """Report PBM backend readiness without letting backend diagnostics crash Environment Check."""
    try:
        from .backend import BackendService
        from .backend.models import BackendStatus

        result = BackendService().verify_backend()
    except Exception as exc:  # noqa: BLE001 - Environment Check must remain safe on clean machines.
        return EnvironmentCheckResult(
            name="PBM managed backend",
            status=CheckStatus.WARNING,
            message=f"Could not verify managed backend: {exc}",
            guidance="Open Mission Control Backend settings, review PBM logs, then install or repair the user-local backend.",
        )

    if result.status is BackendStatus.READY:
        backend_python = getattr(getattr(result, "state", None), "python_executable", None)
        python_text = f" Backend Python: {backend_python}." if backend_python else ""
        return EnvironmentCheckResult(
            name="PBM managed backend",
            status=CheckStatus.PASS,
            message=f"PBM Backend: READY.{python_text} Routed products can run without installing PyForestScan or PDAL into QGIS Python.",
            guidance="PBM-routed products: Dataset Explorer local inspection, CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic.",
        )
    if result.status is BackendStatus.REPAIR_REQUIRED:
        return EnvironmentCheckResult(
            name="PBM managed backend",
            status=CheckStatus.WARNING,
            message=f"Managed backend requires repair: {result.summary}",
            guidance="Use Mission Control Backend settings to view logs, repair, or retry installation. QGIS Python is not modified.",
        )
    return EnvironmentCheckResult(
        name="PBM managed backend",
        status=CheckStatus.WARNING,
        message=f"Managed backend status: {result.status.value}. {result.summary}",
        guidance="Install PBM backend from Mission Control on supported internal beta builds, or continue with QGIS Python dependencies.",
    )


def _no_manual_setup_scope_check(selected_backend: EnvironmentCheckResult) -> EnvironmentCheckResult:
    """Explain which workflows no longer require manual QGIS Python setup."""
    if "Backend Manager" in selected_backend.message or "PBM" in selected_backend.message:
        return EnvironmentCheckResult(
            name="No-manual-setup scope",
            status=CheckStatus.PASS,
            message="Dataset Explorer local inspection and PBM-routed products can use PBM backend without PyForestScan/PDAL in QGIS Python.",
            guidance="PBM-routed: CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic. QGIS-Python-only remaining: Height Above Ground point-cloud export and Preprocess Point Cloud.",
        )
    return EnvironmentCheckResult(
        name="No-manual-setup scope",
        status=CheckStatus.WARNING,
        message="No-manual-setup processing is unavailable until PBM backend is READY.",
        guidance="Install or repair PBM backend, then rerun Environment Check.",
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
