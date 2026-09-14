"""QGIS-free Phase 28D reliability regression tests."""
import tempfile, unittest
from pathlib import Path
from pyforestscan_qgis.core.processing_monitor import ProcessingTimeoutPolicy, TimeoutMode, classify_raster_workload, evaluate_liveness
from pyforestscan_qgis.core.job_identity import ProcessingJobIdentity, output_matches_attempt
from pyforestscan_qgis.core.output_registry import automatic_load_paths, generated_output_for_path
from pyforestscan_qgis.core.project_session import ProjectSessionStore, footer_status

class LongJobTests(unittest.TestCase):
 def test_active_beyond_hour_remains_running(self):
  p=ProcessingTimeoutPolicy.automatic(); self.assertEqual(evaluate_liveness(p,elapsed=7200,heartbeat_age=2,progress_age=4000).status,"running"); self.assertIsNone(p.maximum_wall_time)
 def test_stall_and_custom_wall_time(self):
  p=ProcessingTimeoutPolicy(); self.assertEqual(evaluate_liveness(p,elapsed=2000,heartbeat_age=1900,progress_age=10).status,"stalled")
  p=ProcessingTimeoutPolicy(mode=TimeoutMode.CUSTOM,maximum_wall_time=60); self.assertEqual(evaluate_liveness(p,elapsed=61,heartbeat_age=1,progress_age=1).status,"timed_out")
 def test_reported_workload_is_large(self):
  e=classify_raster_workload((204844.552241,2215636.79077,215834.474587,2222304.47742),1.0,"chm","ept")
  self.assertEqual((e.columns,e.rows,e.cells),(10990,6668,73281320)); self.assertEqual(e.classification,"Large")

class OutputIsolationTests(unittest.TestCase):
 def test_only_current_attempt_loads(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"chm.tif";p.write_bytes(b"x")
   old=generated_output_for_path(p,job_id="old",attempt_id="a1",project_identity="A")
   cur=generated_output_for_path(p,job_id="new",attempt_id="a2",project_identity="B")
   self.assertEqual(automatic_load_paths((old,cur),job_id="new",attempt_id="a2",project_identity="B"),(p,))
   self.assertEqual(automatic_load_paths((old,),job_id="new",attempt_id="a2"),())
 def test_identity_sidecar_required(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"chm.tif";p.write_bytes(b"x");i=ProcessingJobIdentity.create(project_identity="A",session_id="S",repository_path="repo",plan_signature="P",output_root=d)
   self.assertFalse(output_matches_attempt(p,i,(p,)));i.write_sidecar(p);self.assertTrue(output_matches_attempt(p,i,(p,)));self.assertNotEqual(i.attempt_id,i.new_attempt().attempt_id)

class ProjectStateTests(unittest.TestCase):
 def test_projects_and_selection_are_isolated(self):
  store=ProjectSessionStore();a=store.state_for("A");a.repository_changed("ept.json","ept");a.polygon_changed("Plot",(1,),1_300_000,"hash")
  b=store.state_for("B");self.assertEqual(b.repository_path,"");self.assertEqual(footer_status("Ready",a),("Ready","EPT selected","130 ha","Needs Prerun Check"))
  a.repository_changed("other","folder");self.assertEqual(a.polygon_geometry_hash,"");self.assertEqual(a.current_outputs,())

if __name__ == '__main__': unittest.main()
