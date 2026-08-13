import tempfile,time,unittest
from pathlib import Path
from pyforestscan_qgis.core.active_job import ActiveProcessingJobController,CurrentJobToken
from pyforestscan_qgis.core.error_taxonomy import ErrorCategory,error_definition
from pyforestscan_qgis.core.job_storage import RetentionCategory,classify_job_path,clean_maintenance_candidates,maintenance_candidates
from pyforestscan_qgis.core.output_registry import generated_output_for_path,outputs_for_current_attempt
from pyforestscan_qgis.core.product_capabilities import PRODUCT_CAPABILITIES,product_capability

class Phase29EHardeningTests(unittest.TestCase):
 def token(self,n):return CurrentJobToken.create("project","session",f"plan-{n}","repo","polygon")
 def test_product_contracts_are_complete_and_product_aware(self):
  for key in ("chm","pad","pai","fhd","rumple","canopy_cover","dtm","point_density","voxel_stat"):
   cap=product_capability(key);self.assertIsNotNone(cap);self.assertTrue(cap.required_dimensions);self.assertTrue(cap.validation_status)
  self.assertEqual("multiband_raster",PRODUCT_CAPABILITIES["pad"].display_role)
  self.assertEqual("table",PRODUCT_CAPABILITIES["rumple"].output_kind)
 def test_output_registry_uses_contract(self):
  with tempfile.TemporaryDirectory() as folder:
   pad=Path(folder)/"pad.tif";pad.touch();rumple=Path(folder)/"rumple.csv";rumple.touch()
   self.assertEqual("pad_rgb_5_3_2",generated_output_for_path(pad,job_id="j").recommended_renderer)
   self.assertEqual("table",generated_output_for_path(rumple,job_id="j").output_kind)
 def test_error_taxonomy_has_actionable_terminal_shape(self):
  item=error_definition("FAILED_EMPTY_READ")
  self.assertEqual(ErrorCategory.COVERAGE,item.category);self.assertTrue(item.user_message);self.assertTrue(item.recommended_action)
  self.assertEqual(ErrorCategory.UNKNOWN,error_definition("future-code").category)
 def test_storage_maintenance_never_selects_required_or_recoverable(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);final=root/"final.tif";final.touch();status=root/"work_units"/"wu-1"/"status.json";status.parent.mkdir(parents=True);status.touch();temp=root/"stale.tmp";temp.touch()
   old=time.time()-1000
   for path in (final,status,temp):path.touch();path.chmod(0o600)
   candidates=maintenance_candidates(root,older_than_seconds=0,now=old+2000)
   self.assertEqual((temp,),tuple(x.path for x in candidates));self.assertTrue(final.exists());self.assertTrue(status.exists())
   clean_maintenance_candidates(candidates,dry_run=False);self.assertFalse(temp.exists());self.assertTrue(final.exists())
 def test_retention_categories(self):
  self.assertEqual(RetentionCategory.REQUIRED,classify_job_path("run/final.tif"))
  self.assertEqual(RetentionCategory.RECOVERABLE,classify_job_path("run/work_units/wu/status.json"))
  self.assertEqual(RetentionCategory.DIAGNOSTIC,classify_job_path("run/diagnostics/job.log"))
 def test_fifty_job_current_historical_isolation_soak(self):
  controller=ActiveProcessingJobController()
  states=("complete","failed","cancelled","scientific_blocker")
  for index in range(50):
   token=self.token(index);controller.begin(token)
   stale=self.token(f"stale-{index}")
   self.assertFalse(controller.update(stale,"complete",("stale.tif",)))
   state=states[index%len(states)];paths=(f"result-{index}.tif",) if state=="complete" else ()
   self.assertTrue(controller.update(token,state,paths));self.assertEqual(token,controller.current.token)
   self.assertLessEqual(len([controller.current]),1)
   self.assertEqual(paths if state=="complete" else (),controller.current_output_paths(token,paths))
  self.assertEqual(49,len(controller.history));self.assertNotIn("stale.tif",sum((x.final_output_paths for x in controller.history),()))
 def test_attempt_registry_rejects_historical_outputs(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/"chm.tif";path.touch()
   old=generated_output_for_path(path,job_id="old",attempt_id="a")
   self.assertEqual((),outputs_for_current_attempt((old,),job_id="new",attempt_id="b"))

if __name__=="__main__":unittest.main()
