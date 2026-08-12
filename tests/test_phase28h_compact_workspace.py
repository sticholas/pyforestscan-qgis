from pathlib import Path
import unittest
from pyforestscan_qgis.ui.smart_status import build_smart_status
ROOT=Path(__file__).resolve().parents[1]
class CompactWorkspaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.mission=(ROOT/'pyforestscan_qgis/ui/mission_control.py').read_text();cls.pages=(ROOT/'pyforestscan_qgis/ui/pages.py').read_text();cls.form=(ROOT/'pyforestscan_qgis/ui/forms/mission_control.ui').read_text()
 def test_only_two_visible_navigation_destinations(self):
  self.assertIn('PAGE_NAMES = ("Process", "Tools & Setup")',self.mission)
  page_contract=self.mission.split('PAGE_NAMES = ',1)[1].split('\n',1)[0]
  self.assertNotIn('Results',page_contract);self.assertNotIn('Environment',page_contract)
 def test_process_combines_current_results(self):
  self.assertIn('create_section("Current Result")',self.pages);self.assertIn('QPushButton("Load into QGIS")',self.pages);self.assertIn('QPushButton("New Run")',self.pages)
 def test_tools_synthesizes_system_and_advanced_access(self):
  self.assertIn('super().__init__("Tools & Setup"',self.pages);self.assertIn('QPushButton("Verify Environment")',self.pages);self.assertIn('QPushButton("Open Processing Toolbox")',self.pages)
 def test_compact_width_and_live_status_strip(self):
  self.assertIn('<width>420</width>',self.form);self.assertIn('self.ui.statusFrame.setVisible(True)',self.mission)
  self.assertIn('compact = self.width() < 620',self.mission)
 def test_smart_status_states(self):
  ready=build_smart_status(backend_ready=True,repository_kind='ept',polygon_area=652000,products=('CHM',),output_folder='out');self.assertEqual(ready.headline,'Ready to process');self.assertIn('65.2 ha polygon',ready.details)
  running=build_smart_status(processing_state='running',completed=18,total=34);self.assertIn('18 of 34',running.details[0])
  complete=build_smart_status(has_outputs=True);self.assertEqual(complete.headline,'Complete')
if __name__=='__main__':unittest.main()
