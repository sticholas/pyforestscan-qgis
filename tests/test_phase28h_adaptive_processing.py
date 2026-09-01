import tempfile,unittest
from pathlib import Path
from pyforestscan_qgis.core.adaptive_processing import AdaptivePlannerInputs,PilotMeasurement,calibrate_from_pilot,derive_adaptive_plan
from pyforestscan_qgis.core.performance_history import PerformanceHistoryCache,PerformanceMeasurement,PerformanceProfileKey
from pyforestscan_qgis.core.source_aware_processing import NativeSource,SourceAwareWorkPlanner,SpatialExtent,WorkUnitType

class AdaptiveScaleTests(unittest.TestCase):
    def plan(self,width,height,**kwargs):
        source=NativeSource(Path(kwargs.pop('path','ept.json')),SpatialExtent(0,0,width,height),source_type=kwargs.pop('source_type','ept'))
        return SourceAwareWorkPlanner().plan(repository_kind=kwargs.pop('repository_kind','ept'),sources=(source,),polygon_envelope=source.bounds,processing_crs='EPSG:26904',product='chm',resolution=kwargs.pop('resolution',1),available_memory_bytes=kwargs.pop('memory',8*1024**3),cpu_count=kwargs.pop('cpu',8),**kwargs)
    def test_scale_matrix_is_derived_without_count_target(self):
        tiny=self.plan(100,100);small=self.plan(400,400);medium=self.plan(2500,2000);large=self.plan(11000,6700);very_large=self.plan(30000,20000)
        self.assertEqual(tiny.required_count,1);self.assertEqual(tiny.adaptive_strategy,'small_safe_request')
        self.assertLessEqual(small.required_count,4);self.assertGreater(medium.required_count,small.required_count)
        self.assertGreater(large.required_count,medium.required_count);self.assertGreater(very_large.required_count,120)
        self.assertNotEqual(very_large.required_count,120)
    def test_network_ept_is_bounded_and_serial_by_default(self):
        plan=self.plan(5000,5000,path='//server/ept.json',profile='performance')
        self.assertEqual(plan.concurrency_limit,1);self.assertTrue(all(unit.unit_type is WorkUnitType.EPT_WINDOW for unit in plan.work_units))
    def test_native_small_tiles_are_reused_without_grid_overlay(self):
        sources=tuple(NativeSource(Path(f'{i}.laz'),SpatialExtent(i*100,0,(i+1)*100,100),10*1024**2,source_type='laz') for i in range(4))
        plan=SourceAwareWorkPlanner().plan(repository_kind='folder',sources=sources,polygon_envelope=SpatialExtent(0,0,400,100),processing_crs='EPSG:26904',product='chm',resolution=1)
        self.assertEqual(plan.required_count,1);self.assertEqual(plan.work_units[0].unit_type,WorkUnitType.GROUPED_SOURCE_FILES);self.assertEqual(plan.native_partitions_reused,4)
    def test_irregular_polygon_filters_after_adaptive_grid(self):
        source=NativeSource(Path('ept.json'),SpatialExtent(0,0,3000,2000),source_type='ept')
        plan=SourceAwareWorkPlanner().plan(repository_kind='ept',sources=(source,),polygon_envelope=source.bounds,processing_crs='EPSG:26904',product='chm',resolution=1,polygon_wkt='POLYGON ((0 0, 3000 0, 500 2000, 0 2000, 0 0))')
        self.assertEqual(plan.skipped_count,0);self.assertEqual(plan.candidate_count,plan.required_count)
        self.assertGreater(plan.outside_polygon_count_estimate,0)
        self.assertGreater(plan.target_work_unit_width,derive_adaptive_plan(AdaptivePlannerInputs(3000,2000,6_000_000,1)).target_width)
    def test_pilot_can_grow_or_shrink_units(self):
        base=derive_adaptive_plan(AdaptivePlannerInputs(5000,5000,25_000_000,1,available_memory_bytes=8*1024**3,cpu_count=8))
        cheap=calibrate_from_pilot(base,PilotMeasurement(1_000_000,1_000_000,2,2,1,100*1024**2,4),8*1024**3,8)
        expensive=calibrate_from_pilot(base,PilotMeasurement(1_000_000,20_000_000,200,200,50,4*1024**3,1),8*1024**3,8)
        self.assertGreater(cheap.target_width,base.target_width);self.assertLess(expensive.target_width,base.target_width)
        self.assertFalse(cheap.pilot_required);self.assertEqual(expensive.concurrency,1)

class PerformanceHistoryTests(unittest.TestCase):
    def test_cache_is_advisory_and_key_changes_invalidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=PerformanceHistoryCache(Path(tmp)/'performance.json');key=PerformanceProfileKey('repo-a','ept','chm',1,'existing','20-30','1')
            value=PerformanceMeasurement(20,1000,1000,50_000_000,10000,1);cache.put(key,value)
            self.assertEqual(cache.get(key).points_per_square_metre,20)
            changed=PerformanceProfileKey('repo-a','ept','chm',2,'existing','20-30','1');self.assertIsNone(cache.get(changed))
            cache.invalidate_repository('repo-a');self.assertIsNone(cache.get(key))

if __name__=='__main__':unittest.main()
