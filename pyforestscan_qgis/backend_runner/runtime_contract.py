"""Self-identity for the code and scientific runtime used by PBM."""

from __future__ import annotations

import hashlib
import importlib
import json
import platform
import os
import sys
import inspect
from importlib import metadata
from pathlib import Path
from typing import Any

from .job_spec import PBM_PROTOCOL_VERSION
from pyforestscan_qgis.core.backend.runtime_manifest import PYFORESTSCAN_FUNCTION_CONTRACT, PROCESSING_ENGINE_DEPENDENCIES, PRODUCT_CAPABILITIES, SUPPORTED_PYFORESTSCAN_VERSION


_DISTRIBUTION_NAMES = {
    "pyforestscan": "pyforestscan",
    "pdal": "pdal",
    "rasterio": "rasterio",
    "numpy": "numpy",
    "osgeo.gdal": "GDAL",
    "scipy": "scipy",
    "shapely": "shapely",
    "pyproj": "pyproj",
    "pandas": "pandas",
}


def inspect_runtime_contract() -> dict[str, Any]:
    """Return protocol, versions, hashes, and actual module locations."""
    from pyforestscan_qgis import __version__
    from pyforestscan_qgis.core import adapter, pipeline
    from pyforestscan_qgis.core.backend.processing_engine import dependency_manifest_hash, product_capability_hash

    runner = Path(__file__).with_name("run_processing_job.py")
    modules = {
        "backend_runner": str(runner),
        "adapter": str(Path(adapter.__file__).resolve()),
        "pipeline": str(Path(pipeline.__file__).resolve()),
    }
    versions: dict[str, str] = {}
    required_modules = tuple(dict.fromkeys((*PYFORESTSCAN_FUNCTION_CONTRACT, *(item.import_name for item in PROCESSING_ENGINE_DEPENDENCIES))))
    failed_required_components: list[str] = []
    function_contract: dict[str, dict[str, bool]] = {}
    function_signatures: dict[str, dict[str, str]] = {}
    for name in required_modules:
        try:
            module = importlib.import_module(name)
            modules[name] = str(Path(module.__file__).resolve()) if getattr(module, "__file__", None) else "built-in"
            versions[name] = _module_version(name, module)
            expected_functions = PYFORESTSCAN_FUNCTION_CONTRACT.get(name, ())
            function_contract[name] = {function: callable(getattr(module, function, None)) for function in expected_functions}
            function_signatures[name] = {
                function: str(inspect.signature(getattr(module, function)))
                for function, available in function_contract[name].items() if available
            }
            failed_required_components.extend(f"{name}.{function}" for function, available in function_contract[name].items() if not available)
        except Exception as exc:  # noqa: BLE001 - identity must remain available when a dependency is broken.
            modules[name] = f"unavailable: {exc}"
            versions[name] = "unavailable"
            failed_required_components.append(name)
    if versions.get("pyforestscan") != SUPPORTED_PYFORESTSCAN_VERSION:
        failed_required_components.append(
            f"pyforestscan.version:{versions.get('pyforestscan', 'unknown')}"
        )
    available_functions = {
        function for checks in function_contract.values() for function, available in checks.items() if available
    }
    capability_smoke = {
        product: all(function in available_functions for function in functions)
        for product, functions in PRODUCT_CAPABILITIES.items()
    }
    failed_required_components.extend(
        f"product_capability:{product}" for product, passed in capability_smoke.items() if not passed
    )
    protocol_compatible = str(PBM_PROTOCOL_VERSION) == "2"
    package_root = Path(__file__).resolve().parents[1]
    build_inputs = (
        runner,
        Path(__file__).with_name("polygon_job_coordinator.py"),
        Path(adapter.__file__).resolve(),
        Path(pipeline.__file__).resolve(),
        package_root / "core" / "backend" / "execution.py",
        package_root / "core" / "polygon_batch.py",
    )
    build_id = hashlib.sha256(b"".join(path.read_bytes() for path in build_inputs)).hexdigest()
    return {
        "backend_api_version": "2",
        "protocol_version": PBM_PROTOCOL_VERSION,
        "plugin_version": getattr(__version__, "full_version", lambda: "unknown")(),
        "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        "plugin_build_id": build_id,
        "dependency_manifest_hash": dependency_manifest_hash(),
        "product_capability_hash": product_capability_hash(tuple(PRODUCT_CAPABILITIES)),
        "installed_plugin_contract": {
            "plugin_version": getattr(__version__, "full_version", lambda: "unknown")(),
            "protocol": PBM_PROTOCOL_VERSION,
            "build_id": build_id,
            "package_root": str(Path(__file__).resolve().parents[2]),
        },
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "working_directory": os.getcwd(),
        "sys_path": list(sys.path),
        "required_modules": list(required_modules),
        "required_functions": function_contract,
        "required_function_signatures": function_signatures,
        "product_capabilities": {name: list(functions) for name, functions in PRODUCT_CAPABILITIES.items()},
        "capability_smoke_results": capability_smoke,
        "failed_required_components": failed_required_components,
        "protocol_compatible": protocol_compatible,
        "versions": versions,
        "module_locations": modules,
    }


def _module_version(name: str, module: object) -> str:
    value = getattr(module, "__version__", None)
    if value:
        return str(value)
    distribution = _DISTRIBUTION_NAMES.get(name)
    if distribution:
        try:
            return metadata.version(distribution)
        except metadata.PackageNotFoundError:
            pass
    return "unknown"


def print_runtime_contract() -> int:
    print(json.dumps(inspect_runtime_contract(), indent=2, sort_keys=True))
    return 0
