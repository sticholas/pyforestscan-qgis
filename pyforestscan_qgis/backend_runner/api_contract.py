"""PBM-side PyForestScan API contract inspection."""

from __future__ import annotations

import importlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs
from typing import Any

from pyforestscan_qgis.core.ept_bounds import ADAPTER_CONTRACT_VERSION


def inspect_api_contract() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "plugin_adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "compatible": False,
        "errors": [],
    }
    try:
        pyforestscan = importlib.import_module("pyforestscan")
        payload["pyforestscan_version"] = getattr(pyforestscan, "__version__", "unknown")
        payload["pyforestscan_path"] = str(Path(getattr(pyforestscan, "__file__", "")).resolve())
    except Exception as exc:  # noqa: BLE001 - diagnostics should be structured.
        payload["errors"].append(f"pyforestscan import failed: {exc}")
    try:
        handlers = importlib.import_module("pyforestscan.handlers")
        read_lidar = getattr(handlers, "read_lidar")
        signature = inspect.signature(read_lidar)
        params = set(signature.parameters)
        payload["read_lidar_signature"] = str(signature)
        payload["bounds_parameter_present"] = "bounds" in params
        payload["crop_poly_parameter_present"] = "crop_poly" in params
        payload["poly_parameter_present"] = "poly" in params
        payload["supported_input_behavior"] = "signature-probed"
    except Exception as exc:  # noqa: BLE001
        payload["errors"].append(f"read_lidar signature probe failed: {exc}")
        payload["bounds_parameter_present"] = False
        payload["crop_poly_parameter_present"] = False
        payload["poly_parameter_present"] = False
    payload["pdal_version"] = _import_version("pdal")
    payload["gdal_version"] = _gdal_version()
    payload["compatible"] = bool(payload.get("bounds_parameter_present") and payload.get("crop_poly_parameter_present") and payload.get("poly_parameter_present") and not payload["errors"])
    return payload


def print_api_contract() -> None:
    print(json.dumps(inspect_api_contract(), indent=2, sort_keys=True))


def _import_version(module_name: str) -> str:
    try:
        module = importlib.import_module(module_name)
        return str(getattr(module, "__version__", "unknown"))
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"


def _gdal_version() -> str:
    try:
        from osgeo import gdal

        return str(gdal.VersionInfo("--version"))
    except Exception:
        pass
    try:
        completed = subprocess.run(["gdalinfo", "--version"], check=False, capture_output=True, text=True, timeout=10, **hidden_subprocess_kwargs())
        return (completed.stdout or completed.stderr).strip() or "unknown"
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"
