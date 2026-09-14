"""Human-readable Processing Engine summary from authoritative state."""

from __future__ import annotations

from .models import BackendRegistry


def format_system_summary(status: str, plugin_version: str, registry: BackendRegistry, message: str = "") -> str:
    dependencies = {item.name: item for item in registry.dependencies}

    def value(name: str) -> str:
        item = dependencies.get(name)
        if item is None:
            return "Not detected"
        if item.detected_version:
            return item.detected_version
        return "Ready" if item.verification_status.value == "pass" else item.verification_status.value.replace("_", " ").title()

    display = {
        "READY": "Ready", "CHECKING": "Checking", "SETUP_REQUIRED": "Setup required",
        "REPAIR_REQUIRED": "Needs attention", "FAILED": "Unavailable", "INCOMPATIBLE": "Update required",
    }.get(status, status.replace("_", " ").title())
    recent_issue = "None" if status == "READY" else (message or "Run Recheck for details.")
    return "\n".join((
        "Technical Status", "",
        f"Processing Engine: {display}",
        f"Python: {value('python')}",
        f"PyForestScan: {value('pyforestscan')}",
        f"PDAL: {value('pdal')}",
        f"GDAL: {value('gdal')}",
        f"Rasterio: {value('rasterio')}",
        f"Plugin: {plugin_version}",
        f"Recent issue: {recent_issue}", "",
        "Open Technical Log for detailed setup and runtime information.",
    ))
