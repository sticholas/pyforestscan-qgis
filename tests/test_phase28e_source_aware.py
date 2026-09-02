"""Phase 28E source-aware planning and scheduler regression tests."""
import json, tempfile, threading, time, unittest
from pathlib import Path
from pyforestscan_qgis.core.hag_strategy import HagStrategyPlanner,assess_hag_suitability,classify_hag_exception
from pyforestscan_qgis.core.processing_monitor import ProcessingTimeoutPolicy,TimeoutMode,evaluate_liveness,has_wall_time_limit,normalized_wall_time
from pyforestscan_qgis.core.raster_mosaic_plan import MosaicInput,MosaicPlan,validate_mosaic_plan
from pyforestscan_qgis.core.source_aware_processing import AlignedRasterGrid,NativeSource,PRODUCT_POLICIES,SourceAwareWorkPlanner,SpatialExtent,WorkUnitType,source_location
from pyforestscan_qgis.core.work_unit_scheduler import CheckpointStore,PolygonProductWorkScheduler,WorkUnitResult

class TimeoutIntegrityTests(unittest.TestCase):
 def test_unlimited_legacy_values(self):
  for value in (None,'', 'None',0,-1,float('inf'),'bad'):
   self.assertIsNone(normalized_wall_time(value))
  self.assertFalse(has_wall_time_limit(ProcessingTimeoutPolicy(maximum_wall_time=None)))
 def test_explicit_wall_limit_only(self):
  p=ProcessingTimeoutPolicy(mode=TimeoutMode.CUSTOM,maximum_wall_time='120')
  self.assertTrue(has_wall_time_limit(p));self.assertEqual(p.wall_time_for('chm'),120)
  self.assertEqual(evaluate_liveness(p,elapsed=121,heartbeat_age=1,progress_age=1).reason,'Configured custom maximum wall time was reached.')

class PlannerTests(unittest.TestCase):
 def setUp(self):self.planner=SourceAwareWorkPlanner();self.extent=SpatialExtent(0,0,10990,6668)
 def test_large_ept_uses_windows_not_nodes(self):
  src=NativeSource(Path('ept.json'),self.extent,source_type='ept')
  plan=self.planner.plan(repository_kind='ept',sources=(src,),polygon_envelope=self.extent,processing_crs='EPSG:6635',product='chm',resolution=1,available_memory_bytes=8*1024**3,cpu_count=4)
  self.assertEqual((plan.grid.columns,plan.grid.rows),(10990,6668));self.assertGreater(len(plan.work_units),1);self.assertEqual(plan.workload_category,'Large');self.assertTrue(all(x.unit_type is WorkUnitType.EPT_WINDOW for x in plan.work_units));self.assertTrue(all(x.source_paths==(Path('ept.json'),) for x in plan.work_units));self.assertFalse(plan.physical_retiling)
 def test_network_caps_concurrency(self):
        src=NativeSource(Path('//server/share/ept.json'),SpatialExtent(0,0,3000,3000),source_type='ept');plan=self.planner.plan(repository_kind='ept',sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:1',product='chm',resolution=1,available_memory_bytes=64*1024**3,cpu_count=16,profile='performance');self.assertEqual(plan.source_location,'network');self.assertLessEqual(plan.concurrency_limit,2)
 def test_native_small_files_group_without_retiling(self):
  src=tuple(NativeSource(Path(f'{i}.laz'),SpatialExtent(i*100,0,(i+1)*100,100),100*1024**2,source_type='laz') for i in range(3));plan=self.planner.plan(repository_kind='folder',sources=src,polygon_envelope=SpatialExtent(0,0,300,100),processing_crs='EPSG:1',product='chm',resolution=1);self.assertEqual(len(plan.work_units),1);self.assertEqual(plan.work_units[0].unit_type,WorkUnitType.GROUPED_SOURCE_FILES);self.assertFalse(plan.physical_retiling)
 def test_distant_native_files_are_not_grouped(self):
  src=(NativeSource(Path('a.laz'),SpatialExtent(0,0,100,100),100),NativeSource(Path('b.laz'),SpatialExtent(5000,0,5100,100),100));plan=self.planner.plan(repository_kind='folder',sources=src,polygon_envelope=SpatialExtent(0,0,5100,100),processing_crs='EPSG:1',product='chm',resolution=1);self.assertEqual(len(plan.work_units),2)
 def test_large_copc_is_bounded(self):
  src=NativeSource(Path('big.copc.laz'),SpatialExtent(0,0,3000,2000),3*1024**3,source_type='copc');plan=self.planner.plan(repository_kind='copc',sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:1',product='chm',resolution=1);self.assertGreater(len(plan.work_units),1);self.assertTrue(all(x.unit_type is WorkUnitType.COPC_WINDOW for x in plan.work_units))
 def test_large_las_subdivides_and_other_products_are_gated(self):
  src=NativeSource(Path('big.laz'),SpatialExtent(0,0,2500,1000),3*1024**3,source_type='laz');plan=self.planner.plan(repository_kind='folder',sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:1',product='chm',resolution=1);self.assertTrue(all(x.unit_type is WorkUnitType.SUBDIVIDED_LARGE_SOURCE for x in plan.work_units));self.assertFalse(PRODUCT_POLICIES['pad'].default_enabled);self.assertRaises(ValueError,self.planner.plan,repository_kind='ept',sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:1',product='pad',resolution=1)
 def test_global_grid_has_no_gaps(self):
  grid=AlignedRasterGrid.from_extent(SpatialExtent(-10.2,-5.1,10.1,5.2),1,'EPSG:1');self.assertEqual((grid.columns,grid.rows),(21,11));a=grid.cell_extent(0,5,0,10);b=grid.cell_extent(0,5,10,21);self.assertEqual(a.xmax,b.xmin);self.assertEqual(grid.total_extent.xmax,10.8)

class HagTests(unittest.TestCase):
 def test_suitable_ground_selects_delaunay(self):
  report=assess_hag_suitability((0,1,0,1),(0,0,1,1),(2,2,2,2),area=1);self.assertEqual(report.status,'Suitable');self.assertEqual(HagStrategyPlanner().select(report).method,'classified_ground_delaunay')
 def test_collinear_detected_early(self):
  report=assess_hag_suitability((0,1,2,3),(0,0,0,0),(2,2,2,2));self.assertEqual(report.xy_rank,1);self.assertIn('XY coordinates rank-deficient',report.reasons);self.assertEqual(HagStrategyPlanner().select(report).method,'unavailable')
 def test_existing_hag_and_dtm_routes(self):
  existing=assess_hag_suitability((0,1,2),(0,0,0),(),dimensions=('HeightAboveGround',),hag_values=(0,1,2));self.assertEqual(HagStrategyPlanner().select(existing).method,'existing_normalized_height')
  dtm=assess_hag_suitability((0,1,2),(0,0,0),(),dtm_available=True);self.assertEqual(HagStrategyPlanner().select(dtm,'dtm.tif').method,'provided_dtm')
 def test_all_points_collinear_error_preserved(self):
  error=classify_hag_exception(RuntimeError('All points collinear'),'wu-7');self.assertEqual(error['code'],'HAG_COLLINEAR_INPUT');self.assertIn('All points collinear',error['original_exception']);self.assertFalse(error['retry_identical'])

class SchedulerTests(unittest.TestCase):
 def _units(self):
  src=NativeSource(Path('ept.json'),SpatialExtent(0,0,2000,1000),source_type='ept');return SourceAwareWorkPlanner().plan(repository_kind='ept',sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:1',product='chm',resolution=1).work_units
 def test_checkpoint_and_genuine_resume(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[]
   def execute(unit,attempt):
    calls.append(unit.work_unit_id);p=Path(d)/f'{unit.work_unit_id}.tif';p.write_bytes(unit.work_unit_id.encode());return WorkUnitResult(unit.work_unit_id,'Complete',p)
   store=CheckpointStore(Path(d)/'checkpoints','signature');first=PolygonProductWorkScheduler(self._units(),execute,store,concurrency=2).run();self.assertEqual(len(calls),len(first));calls.clear();second=PolygonProductWorkScheduler(self._units(),execute,store,concurrency=2).run();self.assertEqual(calls,[]);self.assertTrue(all(x.status=='Complete' for x in second))
 def test_transient_retry_and_deterministic_failure(self):
  with tempfile.TemporaryDirectory() as d:
   seen={}
   class Transient(Exception):pass
   def execute(unit,attempt):
    seen[unit.work_unit_id]=attempt
    if unit.work_unit_id.endswith('1') and attempt==1:raise Transient('network')
    if unit.work_unit_id.endswith('2'):raise ValueError('All points collinear')
    p=Path(d)/f'{unit.work_unit_id}.tif';p.write_bytes(b'x');return WorkUnitResult(unit.work_unit_id,'Complete',p)
   units=self._units();out=PolygonProductWorkScheduler(units,execute,CheckpointStore(Path(d)/'cp','sig'),concurrency=2,retry_count=2,transient=lambda e:isinstance(e,Transient)).run();self.assertEqual(seen[units[0].work_unit_id],2);self.assertEqual(seen[units[1].work_unit_id],1);self.assertEqual(out[1].status,'Failed')
 def test_progress_has_real_counts_and_eta_is_conditional(self):
  with tempfile.TemporaryDirectory() as d:
   events=[]
   def execute(unit,attempt):p=Path(d)/f'{unit.work_unit_id}.tif';p.write_bytes(b'x');return WorkUnitResult(unit.work_unit_id,'Complete',p)
   PolygonProductWorkScheduler(self._units(),execute,CheckpointStore(Path(d)/'cp','sig'),progress_callback=events.append).run();self.assertEqual(events[-1].completed,events[-1].total);self.assertEqual(events[-1].active,0);self.assertGreaterEqual(events[-1].elapsed_seconds,0)

class MosaicTests(unittest.TestCase):
 def test_only_verified_aligned_core_inputs(self):
  with tempfile.TemporaryDirectory() as d:
   src=NativeSource(Path('ept.json'),SpatialExtent(0,0,1000,1000),source_type='ept');plan=SourceAwareWorkPlanner().plan(repository_kind='ept',sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:1',product='chm',resolution=1);p=Path(d)/'tile.tif';p.write_bytes(b'x');m=MosaicPlan((MosaicInput(plan.work_units[0],p,True,'EPSG:1',1,-9999),),Path(d)/'final.tif',plan.grid);self.assertEqual(validate_mosaic_plan(m),());bad=MosaicPlan((MosaicInput(plan.work_units[0],p,False,'EPSG:2',2,-9999),),Path(d)/'bad.tif',plan.grid);self.assertGreaterEqual(len(validate_mosaic_plan(bad)),3)

if __name__=='__main__':unittest.main()
