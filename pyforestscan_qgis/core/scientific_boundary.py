"""Enforce that production science runs only inside the managed engine."""

from __future__ import annotations

import os
import sys

SCIENTIFIC_MODULE_PREFIXES = ("pyforestscan", "pdal", "rasterio", "osgeo.gdal")


def managed_engine_active() -> bool:
    return os.environ.get("PYFORESTSCAN_MANAGED_ENGINE") == "1"


def qgis_runtime_active() -> bool:
    return "qgis" in sys.modules or "qgis.core" in sys.modules


def assert_scientific_import_allowed(module_name: str) -> None:
    """Reject accidental QGIS-Python science while allowing managed runner imports."""
    if module_name.startswith(SCIENTIFIC_MODULE_PREFIXES) and qgis_runtime_active() and not managed_engine_active():
        raise RuntimeError(
            "SCIENTIFIC_RUNTIME_BOUNDARY: scientific packages cannot execute inside QGIS Python. "
            f"QGIS Python attempted scientific import {module_name}."
        )
