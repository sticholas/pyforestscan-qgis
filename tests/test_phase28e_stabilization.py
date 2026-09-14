"""Phase 28E stabilization regression and lifecycle soak tests."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pyforestscan_qgis.core.backend.native_worker import classify_worker_exit,write_native_crash_bundle
from pyforestscan_qgis.core.backend.process_env import build_clean_subprocess_env,conda_environment_data_env,native_environment_diagnostics
from pyforestscan_qgis.core.hag_strategy import HagReasonCode,assess_hag_suitability
from pyforestscan_qgis.core.job_diagnostics import classify_exception
from pyforestscan_qgis.core.source_aware_processing import NativeSource,SourceAwareWorkPlanner,SpatialExtent,WorkUnit,WorkUnitType
from pyforestscan_qgis.core.work_unit_scheduler import CheckpointStore,PolygonProductWorkScheduler,WorkFailureCircuitBreaker,WorkUnitResult

class HagStabilityTests(unittest.TestCase):
 def test_full_suitability_contract_and_ground_rank(self):
  report=assess_hag_suitability([0,1,2,3],[0,1,2,3],[2,2,2,2],z=[1,2,3,4],work_unit_id='wu-3')
  self.assertFalse(report.suitable);self.assertEqual(report.reason_code,HagReasonCode.ALL_POINTS_COLLINEAR.value);self.assertEqual(report.ground_xy_rank,1);self.assertEqual(report.work_unit_id,'wu-3');self.assertEqual(report.z_range,3)
 def test_ground_collinear_is_distinct(self):
  report=assess_hag_suitability([0,1,2,0],[0,0,0,2],[2,2,2,5])
  self.assertEqual(report.reason_code,HagReasonCode.GROUND_POINTS_COLLINEAR.value)
 def test_empty_and_collinear_are_nonretryable_actionable_errors(self):
  for message,code in [('All points collinear','HAG_COLLINEAR_INPUT'),('PyForestScan returned empty point arrays','EMPTY_SPATIAL_READ')]:
   try:raise RuntimeError(message)
   except RuntimeError as exc:error=classify_exception(exc)
   self.assertEqual(error.code,code);self.assertFalse(error.retryable);self.assertNotIn('Environment Check',error.suggested_actions)

class NativeIsolationTests(unittest.TestCase):
 def test_qgis_native_paths_and_variables_are_removed(self):
  base={'PATH':r'C:\Program Files\QGIS 3.44.9\bin;C:\OSGeo4W\bin;C:\Windows\System32','QGIS_PREFIX_PATH':'bad','QT_PLUGIN_PATH':'bad','GDAL_DATA':r'C:\QGIS\share\gdal','SSL_CERT_FILE':r'C:\QGIS\curl-ca-bundle.crt','TEMP':r'C:\Temp'}
  env=build_clean_subprocess_env(base,prepend_paths=(Path(r'C:\PBM\env'),Path(r'C:\PBM\env\Library\bin')),extra_env={'GDAL_DATA':r'C:\PBM\env\Library\share\gdal','PROJ_DATA':r'C:\PBM\env\Library\share\proj'})
  joined=env.get('PATH',env.get('Path','')).lower();self.assertNotIn('qgis',joined);self.assertNotIn('osgeo4w',joined);self.assertNotIn('QGIS_PREFIX_PATH',env);self.assertNotIn('QT_PLUGIN_PATH',env);self.assertEqual(env['GDAL_DATA'],r'C:\PBM\env\Library\share\gdal');self.assertTrue(native_environment_diagnostics(env)['isolated'])
 def test_windows_access_violation_beats_warning_stderr(self):
  result=classify_worker_exit(-1073741819,False,'GDAL FutureWarning')
  self.assertTrue(result.native_crash);self.assertEqual(result.exception_status,'0xC0000005');self.assertEqual(result.error_code,'NATIVE_BACKEND_CRASH');self.assertNotIn('FutureWarning',result.user_message)
 def test_parent_writes_native_bundle_without_worker_result(self):
  with tempfile.TemporaryDirectory() as folder:
   info=classify_worker_exit(-1073741819,False);path=write_native_crash_bundle(Path(folder),exit_info=info,command=['python.exe','worker'],executable=Path('python.exe'),pid=13,stdout='',stderr='warning',heartbeat={'stage':'Reading LiDAR'})
   self.assertTrue((path/'process_exit.json').is_file());self.assertEqual(json.loads((path/'terminal_event.json').read_text())['pid'],13)

class SchedulerStabilityTests(unittest.TestCase):
 def units(self,count=120):
  units=[]
  for index in range(count):
   core=SpatialExtent(index*1000,0,(index+1)*1000,1000)
   units.append(WorkUnit(f'wu-{index+1:04d}',WorkUnitType.EPT_WINDOW,(Path('ept.json'),),core,core.buffered(50),0,1000,index*1000,(index+1)*1000,index+1,1))
  return tuple(units)
 def test_ept_profile_exposes_capacity_to_adaptive_controller(self):
  with patch.dict(os.environ,{},clear=False):
   os.environ.pop('PYFORESTSCAN_DEV_EPT_PARALLEL',None);extent=SpatialExtent(0,0,3000,3000);src=NativeSource(Path('ept.json'),extent,source_type='ept');plan=SourceAwareWorkPlanner().plan(repository_kind='ept',sources=(src,),polygon_envelope=extent,processing_crs='EPSG:1',product='chm',resolution=1,cpu_count=16,available_memory_bytes=64*1024**3,profile='performance')
  self.assertGreaterEqual(plan.concurrency_limit,1);self.assertLessEqual(plan.concurrency_limit,5);self.assertTrue(any('adaptive' in note.lower() for note in plan.scientific_assumptions))
 def test_sanitized_120_unit_fixture_stops_after_three_neighbor_failures(self):
  units=self.units();events=[]
  with tempfile.TemporaryDirectory() as folder:
   calls=[]
   def execute(unit,attempt):
    calls.append(unit.work_unit_id)
    if len(calls)<=2:
     output=Path(folder)/(unit.work_unit_id+'.tif');output.write_bytes(b'ok');return WorkUnitResult(unit.work_unit_id,'Complete',output)
    return WorkUnitResult(unit.work_unit_id,'Failed',error_code='HAG_COLLINEAR_INPUT',message='All points collinear')
   result=PolygonProductWorkScheduler(units,execute,CheckpointStore(Path(folder)/'cp','fixture'),concurrency=1,progress_callback=events.append).run()
   self.assertEqual(len(calls),5);self.assertEqual(sum(x.status=='Complete' for x in result),2);self.assertEqual(sum(x.status=='Failed' for x in result),3);self.assertEqual(sum(x.status=='Pending' for x in result),115);self.assertIn('paused',events[-1].stop_reason.lower());self.assertEqual(events[-1].attempted,5);self.assertEqual(events[-1].pending,115)
 def test_repeated_native_crash_stops_queue(self):
  with tempfile.TemporaryDirectory() as folder:
   calls=[]
   def execute(unit,attempt):calls.append(unit.work_unit_id);return WorkUnitResult(unit.work_unit_id,'Failed',error_code='NATIVE_BACKEND_CRASH',message='native crash')
   result=PolygonProductWorkScheduler(self.units(10),execute,CheckpointStore(Path(folder),'native'),concurrency=1).run();self.assertEqual(len(calls),2);self.assertEqual(sum(x.status=='Pending' for x in result),8)
 def test_durable_transition_and_restart_reconciliation(self):
  with tempfile.TemporaryDirectory() as folder:
   store=CheckpointStore(Path(folder),'sig');unit=self.units(1)[0];store.mark_pending(unit);self.assertEqual(store.load(unit.work_unit_id)['status'],'Pending');store.mark_starting(unit,1);self.assertEqual(store.load(unit.work_unit_id)['status'],'Starting');store.mark_running(unit,1,pid=999);self.assertEqual(store.load(unit.work_unit_id)['pid'],999);self.assertEqual(store.reconcile(unit.work_unit_id,pid_alive=lambda pid:False),'Interrupted');self.assertEqual(store.load(unit.work_unit_id)['error_code'],'INTERRUPTED_WORKER')
 def test_120_success_transitions_do_not_retain_active_workers(self):
  units=self.units();events=[]
  with tempfile.TemporaryDirectory() as folder:
   def execute(unit,attempt):output=Path(folder)/(unit.work_unit_id+'.tif');output.write_bytes(b'x');return WorkUnitResult(unit.work_unit_id,'Complete',output)
   result=PolygonProductWorkScheduler(units,execute,CheckpointStore(Path(folder)/'cp','soak'),concurrency=1,progress_callback=events.append).run()
   self.assertEqual(len(result),120);self.assertTrue(all(x.status=='Complete' for x in result));self.assertEqual(events[-1].active,0);self.assertEqual(events[-1].attempted,120)

if __name__=='__main__':unittest.main()
