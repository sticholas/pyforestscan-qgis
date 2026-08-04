"""QGIS-free tests for retained-interface state and toolbox actions."""
from pathlib import Path
import unittest

from pyforestscan_qgis.core.qgis_processing_toolbox import QgisProcessingToolboxService
from pyforestscan_qgis.ui.session_state import MissionControlSessionState, build_scientific_advisor_summary

ROOT = Path(__file__).resolve().parents[1]

class _Algorithm:
    def __init__(self, group): self._group = group
    def group(self): return self._group

class _Provider:
    def __init__(self): self.refreshes = 0
    def algorithms(self): return [_Algorithm("Metrics"), _Algorithm("Terrain")]
    def refreshAlgorithms(self): self.refreshes += 1

class _Registry:
    def __init__(self, provider=None): self.provider = provider; self.adds = 0
    def providerById(self, provider_id): return self.provider if provider_id == "pyforestscan" else None
    def addProvider(self, provider): self.provider = provider; self.adds += 1

class _Dock:
    def __init__(self): self.visible = False; self.raised = False
    def windowTitle(self): return "Processing Toolbox"
    def objectName(self): return ""
    def show(self): self.visible = True
    def setVisible(self, value): self.visible = value
    def isVisible(self): return self.visible
    def raise_(self): self.raised = True
    def activateWindow(self): self.raised = True

class _Window:
    def __init__(self, dock): self.dock = dock
    def findChildren(self, _kind): return [self.dock]

class _Iface:
    def __init__(self, dock): self.dock = dock; self.opens = 0
    def mainWindow(self): return _Window(self.dock)
    def openProcessingToolbox(self): self.opens += 1

class Phase28BStateTests(unittest.TestCase):
    def test_polygon_change_updates_signature_and_summary(self):
        base = MissionControlSessionState(current_mode="polygon", repository_path="ept.json",
            repository_kind="EPT dataset", polygon_geometry_signature="one", polygon_area=1_300_000,
            selected_products=("CHM",), output_folder="D:/tmp")
        first = build_scientific_advisor_summary(base)
        second = build_scientific_advisor_summary(base.with_updates(polygon_geometry_signature="two", polygon_area=900_000))
        self.assertNotEqual(first.source_signature, second.source_signature)
        self.assertIn("130 ha", first.executive_summary)
        self.assertIn("90 ha", second.executive_summary)

    def test_clearing_polygon_removes_area_guidance(self):
        state = MissionControlSessionState(current_mode="polygon", repository_path="repo", polygon_area=5,
                                           polygon_geometry_signature="")
        summary = build_scientific_advisor_summary(state)
        self.assertEqual("Choose a polygon layer or vector file to receive area-specific guidance.", summary.executive_summary)
        self.assertNotIn("5", summary.executive_summary)

    def test_repository_products_and_resolution_affect_signature(self):
        base = MissionControlSessionState(repository_path="a", selected_products=("CHM",), output_resolution=1)
        changed = base.with_updates(repository_path="b", selected_products=("DTM",), output_resolution=2)
        self.assertNotEqual(base.advisor_signature(), changed.advisor_signature())
        self.assertIn("2", build_scientific_advisor_summary(changed).parameter_recommendations[0])

    def test_plan_invalidation(self):
        state = MissionControlSessionState(current_execution_plan=object(), plan_signature="old", plan_status="ready")
        result = state.invalidate_plan()
        self.assertIsNone(result.current_execution_plan)
        self.assertEqual("needs refresh", result.plan_status)

class Phase28BToolboxTests(unittest.TestCase):
    def test_open_finds_shows_and_focuses_toolbox(self):
        dock = _Dock(); registry = _Registry(_Provider())
        result = QgisProcessingToolboxService(_Iface(dock), registry).open_toolbox()
        self.assertTrue(result.success); self.assertTrue(result.toolbox_visible)
        self.assertTrue(result.provider_found); self.assertTrue(result.focused); self.assertTrue(dock.raised)

    def test_provider_status_and_refresh_do_not_duplicate(self):
        provider = _Provider(); registry = _Registry(provider)
        service = QgisProcessingToolboxService(_Iface(_Dock()), registry)
        status = service.refresh_provider(lambda: _Provider())
        self.assertEqual(0, registry.adds); self.assertEqual(1, provider.refreshes)
        self.assertEqual(2, status.algorithm_count)
        self.assertEqual(("Metrics", "Terrain"), status.groups)

    def test_missing_provider_is_actionable(self):
        status = QgisProcessingToolboxService(_Iface(_Dock()), _Registry()).provider_status()
        self.assertFalse(status.available)
        self.assertIn("not registered", status.message)

    def test_sidebar_and_hidden_pages_contract(self):
        mission = (ROOT / "pyforestscan_qgis/ui/mission_control.py").read_text()
        pages = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text()
        for name in ("Batch", "Results", "Scientific Advisor", "Environment", "Settings", "Advanced Toolbox"):
            self.assertIn(f'"{name}"', mission)
        self.assertIn("sessionStateChanged", pages)
        self.assertIn("refresh_from_session", pages)
        self.assertIn("Guidance is updating", pages)

if __name__ == "__main__": unittest.main()
