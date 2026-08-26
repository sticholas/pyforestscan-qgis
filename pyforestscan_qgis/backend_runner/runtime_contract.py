"""Self-identity for the code and scientific runtime used by PBM."""

from __future__ import annotations

import hashlib
import importlib
import json
import platform
import os
import sys
from pathlib import Path
from typing import Any

from .job_spec import PBM_PROTOCOL_VERSION


def inspect_runtime_contract() -> dict[str, Any]:
    """Return protocol, versions, hashes, and actual module locations."""
    from pyforestscan_qgis import __version__
    from pyforestscan_qgis.core import adapter, pipeline

    runner = Path(__file__).with_name("run_processing_job.py")
    modules = {
        "backend_runner": str(runner),
        "adapter": str(Path(adapter.__file__).resolve()),
        "pipeline": str(Path(pipeline.__file__).resolve()),
    }
    versions: dict[str, str] = {}
    required_modules = (
        "pyforestscan",
        "pyforestscan.handlers",
        "pyforestscan.calculate",
        "pyforestscan.filters",
        "pyforestscan.process",
        "pdal",
        "rasterio",
        "numpy",
        "osgeo.gdal",
    )
    failed_required_components: list[str] = []
    for name in required_modules:
        try:
            module = importlib.import_module(name)
            modules[name] = str(Path(module.__file__).resolve()) if getattr(module, "__file__", None) else "built-in"
            versions[name] = str(getattr(module, "__version__", "unknown"))
        except Exception as exc:  # noqa: BLE001 - identity must remain available when a dependency is broken.
            modules[name] = f"unavailable: {exc}"
            versions[name] = "unavailable"
            failed_required_components.append(name)
    protocol_compatible = str(PBM_PROTOCOL_VERSION) == "2"
    return {
        "backend_api_version": "2",
        "protocol_version": PBM_PROTOCOL_VERSION,
        "plugin_version": getattr(__version__, "full_version", lambda: "unknown")(),
        "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "working_directory": os.getcwd(),
        "sys_path": list(sys.path),
        "required_modules": list(required_modules),
        "failed_required_components": failed_required_components,
        "protocol_compatible": protocol_compatible,
        "versions": versions,
        "module_locations": modules,
    }


def print_runtime_contract() -> int:
    print(json.dumps(inspect_runtime_contract(), indent=2, sort_keys=True))
    return 0
