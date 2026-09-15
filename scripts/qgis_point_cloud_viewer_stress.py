#!/usr/bin/env python3
"""Run the real QGIS point-cloud view-switch qualification sequence.

This script is intentionally QGIS-runtime gated. It does not replace the
human GPU/interaction check; it catches lifecycle, sizing, and ownership
regressions while repeatedly moving one verified source through linked views.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path


def _wait(app, predicate, timeout: float, label: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise TimeoutError(f"Timed out waiting for {label}.")


def _bounds(page):
    state = page._view_state or {}
    diagnostics = state.get("render_diagnostics") or {}
    raw = diagnostics.get("root_bounds") or state.get("source_bounds")
    if not isinstance(raw, dict):
        raise RuntimeError("The viewer did not expose source bounds after opening.")
    minimum, maximum = raw.get("min"), raw.get("max")
    if not (isinstance(minimum, (list, tuple)) and isinstance(maximum, (list, tuple))):
        raise RuntimeError("Viewer source bounds are not available in the expected form.")
    if len(minimum) < 3 or len(maximum) < 3:
        raise RuntimeError("Viewer source bounds are incomplete.")
    return tuple(float(value) for value in minimum[:3]), tuple(float(value) for value in maximum[:3])


def _metric(page):
    linked = page.linked
    workers = [worker for worker in linked.viewer_workers() if worker is not None]
    return {
        "active_view": page.workspace.active_view_id,
        "rendered_view": linked.rendered_id,
        "surface": [page.surface.width(), page.surface.height()],
        "tabs": [page.view_tabs.width(), page.view_tabs.height(),
                 page.view_tabs.sizeHint().width(), page.view_tabs.sizeHint().height()],
        "worker_count": len({id(worker) for worker in workers}),
        "renderer_owner_count": int(page.worker is not None) + len(linked.detached),
        "resident_count": len(linked.residents.parked),
    }


def run(source: str, *, cycles: int = 50, timeout: float = 30.0) -> dict:
    from qgis.PyQt.QtWidgets import QApplication
    from qgis.core import QgsApplication
    from pyforestscan_qgis.core.point_cloud.workspace import AreaGeometry, SliceGeometry, ViewType
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage

    app = QApplication.instance() or QgsApplication([], False)
    owns_qgis = isinstance(app, QgsApplication)
    if owns_qgis:
        app.initQgis()
    page = PointCloudPage()
    page.resize(1280, 900)
    page.show()
    metrics = []
    try:
        page.start_source(str(Path(source).resolve()))
        _wait(app, lambda: bool(page._view_state and page._view_state.get("ready")), timeout, "verified overview")
        minimum, maximum = _bounds(page)
        crs = page.linked.source_crs() or "SOURCE_LOCAL:viewer"
        width = max((maximum[0] - minimum[0]) * 0.1, 0.001)
        center = ((minimum[0] + maximum[0]) / 2, (minimum[1] + maximum[1]) / 2)
        area_id = page.linked.add(ViewType.AREA_DETAIL, asdict(
            AreaGeometry("SQUARE", crs, center, width, width)))
        slice_id = page.linked.add(ViewType.VERTICAL_SLICE, asdict(
            SliceGeometry((center[0] - width / 2, center[1]),
                          (center[0] + width / 2, center[1]),
                          max(width * 0.05, 0.001), crs)))
        sequence = (page.overview_id, area_id, slice_id)
        for cycle in range(1, cycles + 1):
            for view_id in sequence:
                page.linked.open_linked_view(view_id)
                _wait(app, lambda view_id=view_id: page.linked.rendered_id == view_id,
                      timeout, f"cycle {cycle} view {view_id}")
                metrics.append({"cycle": cycle, **_metric(page)})
        surfaces = [item["surface"] for item in metrics]
        passed = (
            len(metrics) == cycles * len(sequence)
            and all(width >= 180 and height >= 180 for width, height in surfaces)
            and max(item["worker_count"] for item in metrics) <= len(sequence)
            and all(item["renderer_owner_count"] <= 1 for item in metrics)
        )
        return {"passed": passed, "cycles": cycles, "sequence": list(sequence), "metrics": metrics}
    finally:
        page.prepare_for_unload()
        page.close()
        page.deleteLater()
        app.processEvents()
        if owns_qgis:
            app.exitQgis()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Verified LAS, LAZ, COPC, or local EPT source")
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=Path("phase34b2_viewer_stress.json"))
    args = parser.parse_args()
    if args.cycles < 50:
        parser.error("--cycles must be at least 50 for the Phase 34B2 gate")
    try:
        result = run(args.source, cycles=args.cycles, timeout=args.timeout)
    except Exception as error:
        result = {"passed": False, "error": str(error), "cycles": args.cycles}
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "metrics"}, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
