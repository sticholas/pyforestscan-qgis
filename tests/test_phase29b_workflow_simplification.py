"""Phase 29B workflow simplification contracts."""
from pathlib import Path
import unittest
from pyforestscan_qgis.core.workspace import WorkspaceSession

ROOT=Path(__file__).resolve().parents[1]
PAGES=(ROOT/'pyforestscan_qgis/ui/pages.py').read_text(encoding='utf-8')
PLUGIN=(ROOT/'pyforestscan_qgis/plugin.py').read_text(encoding='utf-8')

class Phase29BWorkflowTests(unittest.TestCase):
 def test_startup_is_opt_in_and_round_trips(self):
  self.assertFalse(WorkspaceSession().open_mission_control_on_startup)
  session=WorkspaceSession.from_dict({'open_mission_control_on_startup':True})
  self.assertTrue(session.open_mission_control_on_startup)
  self.assertTrue(session.to_dict()['open_mission_control_on_startup'])
  self.assertIn('if auto_open:',PLUGIN)
  init_body=PLUGIN.split('def initGui',1)[1].split('def unload',1)[0]
  self.assertIn('if auto_open:',init_body)
 def test_duplicate_repository_and_spatial_buttons_removed(self):
  for label in ('QPushButton("Use Path")','QPushButton("Refresh Catalog Status")','QPushButton("Inspect Data Folder")','QPushButton("Re-run Prerun Check")','QPushButton("Zoom to Combined Extent")'):
   self.assertNotIn(label,PAGES)
  self.assertIn('QPushButton("Prepare Repository")',PAGES)
 def test_spatial_actions_refresh_plan_on_demand(self):
  self.assertIn('def _current_spatial_report',PAGES)
  self.assertIn('self.run_preflight()',PAGES)
 def test_custom_owns_topology_controls(self):
  self.assertIn('custom = self.processing_profile_combo.currentData() == "custom"',PAGES)
  self.assertIn('Upper limit; adaptive planning may use fewer workers',PAGES)
 def test_processing_inputs_share_invalidation(self):
  self.assertIn('self.mask_engine_combo',PAGES)
  self.assertIn('option.toggled.connect(self._on_session_input_changed)',PAGES)

if __name__=='__main__':unittest.main()
