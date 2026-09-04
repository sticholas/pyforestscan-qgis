"""Inventory visible Mission Control controls in a real QGIS runtime."""

from __future__ import annotations

import json
from pathlib import Path

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtWidgets import QAbstractButton, QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox

from pyforestscan_qgis.ui.mission_control import MissionControlDock


INTERACTIVE_TYPES = (QAbstractButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox)
GENERIC_PHRASES = (
    "this option", "this value", "this workflow", "continue this action",
    "use this control", "choose this option", "current workflow",
)


def _identity(widget: object) -> str:
    text = getattr(widget, "text", lambda: "")()
    return str(text or getattr(widget, "objectName", lambda: "")() or type(widget).__name__)


def run() -> dict[str, object]:
    app = QgsApplication.instance() or QgsApplication([], False)
    app.initQgis()
    dock = MissionControlDock(None)
    dock.show()
    app.processEvents()
    pages: list[dict[str, object]] = []
    total = covered = 0
    generic: list[str] = []
    missing: list[str] = []
    inaccessible: list[str] = []
    try:
        for name, page in zip(dock.INTERNAL_PAGE_NAMES, dock.pages):
            dock.ui.pageStack.setCurrentWidget(page)
            app.processEvents()
            page._install_context_help()
            controls = [
                item for item in page.findChildren(INTERACTIVE_TYPES)
                if item.isVisible() and not (
                    isinstance(item, QLineEdit)
                    and isinstance(item.parent(), (QSpinBox, QDoubleSpinBox))
                )
            ]
            page_missing: list[str] = []
            for control in controls:
                total += 1
                identity = f"{name}: {_identity(control)}"
                help_text = str(control.property("resolvedContextHelp") or "").strip()
                if help_text:
                    covered += 1
                else:
                    page_missing.append(identity)
                    missing.append(identity)
                if any(phrase in help_text.lower() for phrase in GENERIC_PHRASES):
                    generic.append(identity)
                if not str(control.accessibleName() or "").strip():
                    inaccessible.append(identity)
            pages.append({"page": name, "visible_controls": len(controls), "missing_help": page_missing})
    finally:
        dock.prepare_for_unload()
        dock.close()
        app.processEvents()
    return {
        "qgis_version": Qgis.QGIS_VERSION,
        "visible_controls": total,
        "help_covered": covered,
        "help_coverage_percent": round(100.0 * covered / total, 1) if total else 100.0,
        "missing_help": missing,
        "generic_help": generic,
        "missing_accessible_name": inaccessible,
        "pages": pages,
        "passed": not missing and not generic and not inaccessible,
    }


if __name__ == "__main__":
    report = run()
    output = Path.cwd() / "phase33a_qgis_control_audit.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
