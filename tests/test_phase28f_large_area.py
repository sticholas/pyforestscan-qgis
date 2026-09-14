import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pyforestscan_qgis.core.atomic_state import atomic_write_json,remove_invalid_temporaries
from pyforestscan_qgis.core.hag_strategy import HagExecutionDecision,assess_hag_suitability
from pyforestscan_qgis.core.resource_estimation import estimate_work_unit_resources
from pyforestscan_qgis.core.work_unit_scheduler import CheckpointStore,WorkFailureCircuitBreaker,WorkUnitResult
from pyforestscan_qgis.backend_runner.job_coordinator import DurableJobCoordinator,ProcessingProgressSnapshot

class Phase28FTests(unittest.TestCase):
 def test_existing_hag_contract(self):
  report=assess_hag_suitability([0,1,0],[0,0,1],[2,2,2],dimensions=["HeightAboveGround"],hag_values=[0,2,5],work_unit_id="wu-3")
  decision=HagExecutionDecision.from_report(report);self.assertEqual(decision.selected_method,"existing_normalized_height");self.assertTrue(decision.method_signature)
  with self.assertRaisesRegex(RuntimeError,"HAG_METHOD_MISMATCH"):decision.assert_executed("classified_ground_delaunay")
 def test_chm_existing_hag_disables_calculation(self):
  from pyforestscan_qgis.core.adapter import _read_lidar_spatial_kwargs
  class R:bounds=None;crop_polygon=None;crop_polygon_path=None;polygon_execution_input=None
  self.assertFalse(_read_lidar_spatial_kwargs(R(),hag=False)["hag"])
 def test_invalid_existing_hag_blocks(self):
  report=assess_hag_suitability([0,1,0],[0,0,1],[2,2,2],dimensions=["HeightAboveGround"],hag_values=[0,0,0]);self.assertFalse(report.suitable)
 def test_memory_is_not_nine_megabytes(self):
  for count in (3_600_000,11_200_000,14_800_000,15_100_000):
   estimate=estimate_work_unit_resources(count);self.assertGreater(estimate.estimated_memory,9_000_000);self.assertNotEqual(estimate.workload_category,"Low")
 def test_unique_atomic_state_and_zero_temp_cleanup(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/"status.json";atomic_write_json(target,{"status":"Complete"});(root/"status.tmp").write_bytes(b"")
   self.assertEqual(json.loads(target.read_text())["status"],"Complete");self.assertEqual(len(remove_invalid_temporaries(root)),1)
 def test_late_worker_result_adopted(self):
  with tempfile.TemporaryDirectory() as folder:
   store=CheckpointStore(Path(folder)/"work","sig");store.save_state("wu-0005","Running",{"pid":999});result=Path(folder)/"result.json";result.write_text(json.dumps({"status":"failed","error_code":"HAG_COLLINEAR_INPUT","errors":["All points collinear"]}))
   self.assertEqual(store.reconcile("wu-0005",pid_alive=lambda _:False,result_path=result),"Failed");self.assertEqual(store.load("wu-0005")["error_code"],"HAG_COLLINEAR_INPUT")
 def test_circuit_breaker_rebuilds_current_failure(self):
  results=[WorkUnitResult(f"wu-{i:04d}","Failed",error_code="HAG_COLLINEAR_INPUT",message="same") for i in (3,4,5)]
  self.assertTrue(WorkFailureCircuitBreaker().rebuild(results).pause)
 def test_durable_command_acknowledgement(self):
  with tempfile.TemporaryDirectory() as folder:
   c=DurableJobCoordinator(folder);identifier=c.command("job","attempt","pause","running");c.acknowledge_commands("job","attempt","running")
   self.assertTrue((Path(folder)/"command_acknowledgements"/f"{identifier}.json").exists())
 def test_polygon_path_submits_to_coordinator(self):
  text=(Path(__file__).parents[1]/"pyforestscan_qgis/core/polygon_batch.py").read_text()
  self.assertIn("_submit_and_observe_source_aware_chm",text);self.assertIn("submit_polygon_coordinator",text)
 def test_coordinator_has_no_qgis_import(self):
  text=(Path(__file__).parents[1]/"pyforestscan_qgis/backend_runner/polygon_job_coordinator.py").read_text()
  self.assertNotIn("from qgis",text);self.assertNotIn("PyQt",text)
 def test_snapshot_survives_observer_absence(self):
  with tempfile.TemporaryDirectory() as folder:
   c=DurableJobCoordinator(folder);c.write_snapshot(ProcessingProgressSnapshot("job","attempt","running",120,2,3,114,1,5,"wu-0005"))
   data=json.loads((Path(folder)/"progress_snapshot.json").read_text());self.assertEqual((data["completed"],data["failed"],data["pending"]),(2,3,114))
if __name__=="__main__":unittest.main()

class Phase28FPlanningTests(unittest.TestCase):
 def test_source_aware_chm_strips_point_polygon_crop(self):
  text=(Path(__file__).parents[1]/"pyforestscan_qgis/core/polygon_batch.py").read_text()
  self.assertIn("crop_polygon=None,crop_polygon_path=None,polygon_execution_input=None",text)
 def test_ept_work_unit_memory_is_conservative(self):
  from pyforestscan_qgis.core.source_aware_processing import NativeSource,SourceAwareWorkPlanner,SpatialExtent
  plan=SourceAwareWorkPlanner().plan(repository_kind="ept",sources=(NativeSource(Path("ept.json"),SpatialExtent(0,0,1000,1000)),),polygon_envelope=SpatialExtent(0,0,1000,1000),processing_crs="EPSG:32610",product="chm",resolution=1)
  self.assertNotEqual(plan.memory_category,"Low");self.assertGreater(plan.work_units[0].estimated_memory,1024**3)
 def test_pilot_is_spatially_distributed(self):
  from pyforestscan_qgis.core.pilot_planning import select_representative_pilot
  self.assertEqual(select_representative_pilot(tuple(range(120))), (0,30,60,90,119))
