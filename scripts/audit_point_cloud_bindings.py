#!/usr/bin/env python3
"""Run with the QGIS Python launcher; emits capability evidence, no data edits."""
import importlib
import json
import sys

TARGETS = {
    "qgis.core": {
        "QgsPointCloudLayer": ["attributes", "pointCount", "setSubsetString", "generateIndex", "startEditing", "rollBack", "changeAttributeValue"],
        "QgsPointCloudLayerRenderer": [],
        "QgsPointCloudLayerEditUtils": [],
        "QgsPointCloudAttributeCollection": ["attributes", "find"],
        "QgsPointCloudRgbRenderer": ["setRedAttribute", "setGreenAttribute", "setBlueAttribute"],
        "QgsPointCloudClassifiedRenderer": ["setCategories"],
        "QgsPointCloudAttributeByRampRenderer": ["setAttribute"],
        "QgsPointCloudLayerElevationProperties": [],
        "QgsPointCloudLayerProfileGenerator": [],
    },
    "qgis._3d": {
        "QgsPointCloudLayer3DRenderer": ["setLayer", "setSymbol", "setPointRenderingBudget", "setMaximumScreenError"],
        "Qgs3DMapCanvas": ["setMapSettings", "mapSettings", "cameraController"],
        "Qgs3DMapSettings": ["setLayers", "setCrs", "setExtent"],
        "QgsCameraController": ["setLookingAtMapPoint", "cameraPose", "setCameraPose"],
    },
    "qgis.gui": {
        "QgisInterface": ["createNewMapCanvas3D", "closeMapCanvas3D"],
        "QgsElevationProfileCanvas": [],
    },
}


def inspect_bindings():
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    result = {"qgis": Qgis.QGIS_VERSION, "qt": QT_VERSION_STR,
              "pyqt": PYQT_VERSION_STR, "python": sys.version, "modules": {}}
    for module_name, classes in TARGETS.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            result["modules"][module_name] = {"error": str(exc)}
            continue
        entries = {}
        for name, methods in classes.items():
            target = getattr(module, name, None)
            available = {method: callable(getattr(target, method, None)) for method in methods}
            entries[name] = {
                "present": target is not None,
                "status": ("UNAVAILABLE_IN_THIS_PYTHON" if target is None else
                           "PARTIALLY_AVAILABLE" if not all(available.values()) else "AVAILABLE_IN_PYTHON"),
                "methods": available,
            }
        result["modules"][module_name] = entries
    for module_name in ("qgis.PyQt.QtWebEngineWidgets", "qgis.PyQt.QtWebKitWidgets"):
        try:
            importlib.import_module(module_name)
            result["modules"][module_name] = {"importable": True}
        except ImportError as exc:
            result["modules"][module_name] = {"importable": False, "error": str(exc)}
    return result


if __name__ == "__main__":
    print(json.dumps(inspect_bindings(), indent=2))
