"""QGIS runtime smoke for Mission Control startup and lifecycle resilience."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

SCIENTIFIC_BASELINE = set(sys.modules)

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QEvent
from qgis.PyQt.QtWidgets import QGroupBox

from pyforestscan_qgis.compat.qt import install_enum_aliases
from pyforestscan_qgis.ui.mission_control import MissionControlDock
from pyforestscan_qgis.ui.pages import SettingsPage
from pyforestscan_qgis.plugin import PyForestScanPlugin

install_enum_aliases(QEvent, "Type", ("DeferredDelete",))


class SmokeIface:
    """Minimal QGIS interface surface used by the plugin-button regression."""

    def __init__(self) -> None:
        self.dock = None

    def mainWindow(self):
        return None

    def addDockWidget(self, _area, dock) -> None:
        self.dock = dock

    def removeDockWidget(self, dock) -> None:
        if self.dock is dock:
            self.dock = None


def engine(status: str, *, ready: bool = False, repair: bool = False) -> object:
    return SimpleNamespace(
        status=SimpleNamespace(value=status),
        ready_for_processing=ready,
        runtime_available=ready,
        repair_needed=repair,
        message=status.replace("_", " ").title(),
    )


def run() -> dict[str, object]:
    app = QgsApplication.instance() or QgsApplication([], False)
    app.initQgis()
    original = SettingsPage.current_processing_engine_state
    states = (
        engine("READY", ready=True),
        engine("SETUP_REQUIRED"),
        engine("REPAIR_REQUIRED", repair=True),
        engine("FAILED"),
    )
    result: dict[str, object] = {"plugin_button": False, "states": [], "widths": {}, "construction_cycles": 0, "navigation_cycles": 0}
    try:
        SettingsPage.current_processing_engine_state = lambda self: engine("SETUP_REQUIRED")
        iface = SmokeIface()
        plugin = PyForestScanPlugin(iface)
        plugin._show_mission_control()
        app.processEvents()
        plugin.mission_control._update_status_bar()
        result["plugin_button"] = iface.dock is plugin.mission_control
        plugin.unload()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

        for state in states:
            print(f"state construction: {state.status.value}", flush=True)
            SettingsPage.current_processing_engine_state = lambda self, state=state: state
            dock = MissionControlDock(None)
            app.processEvents()
            dock._update_status_bar()
            dock.settings_page.set_processing_engine_state(state)
            dock.batch_page.set_processing_engine_state(state)
            dock.results_page.refresh_results()
            result["states"].append({
                "status": state.status.value,
                "ui_available": dock.application_availability.ui_available,
                "processing_available": dock.application_availability.processing_available,
            })
            dock.prepare_for_unload()
            dock.close()
            dock.deleteLater()
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            print(f"state complete: {state.status.value}", flush=True)

        SettingsPage.current_processing_engine_state = lambda self: engine("SETUP_REQUIRED")
        for _ in range(100):
            dock = MissionControlDock(None)
            app.processEvents()
            dock._update_status_bar()
            dock.prepare_for_unload()
            dock.close()
            dock.deleteLater()
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            result["construction_cycles"] += 1
            if result["construction_cycles"] % 10 == 0:
                print(f"construction cycles: {result['construction_cycles']}", flush=True)

        dock = MissionControlDock(None)
        dock.show()
        dock._navigate_to("Tools & Setup")
        app.processEvents()
        for width in (420, 500, 620, 800):
            dock.resize(width, 760)
            app.processEvents()
            result["widths"][str(width)] = {
                "constructed": True,
                "horizontal_scrollbar_visible": dock.settings_page.scroll_area.horizontalScrollBar().isVisible(),
                "advanced_settings_visible": any(
                    group.title() == "Advanced Settings" and group.isVisible()
                    for group in dock.settings_page.findChildren(QGroupBox)
                ),
            }
        for index in range(100):
            dock._navigate_to("Process" if index % 2 == 0 else "Tools & Setup")
            dock._set_processing_engine_state(states[index % len(states)])
            app.processEvents()
            result["navigation_cycles"] += 1
        dock.prepare_for_unload()
        dock.close()
        dock.deleteLater()
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    finally:
        SettingsPage.current_processing_engine_state = original

    scientific = {"pyforestscan", "pdal", "rasterio"}
    result["new_scientific_imports"] = sorted(scientific.intersection(set(sys.modules) - SCIENTIFIC_BASELINE))
    widths_pass = all(
        item["constructed"] and not item["horizontal_scrollbar_visible"]
        for item in result["widths"].values()
    )
    result["passed"] = result["plugin_button"] and result["construction_cycles"] == 100 and result["navigation_cycles"] == 100 and widths_pass and not result["new_scientific_imports"]
    return result


if __name__ == "__main__":
    report = run()
    output = Path.cwd() / "phase32b_qgis_ui_startup.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
