import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pyforestscan_qgis.backend_runner.job_coordinator import aggregate_work_unit_statuses
from pyforestscan_qgis.core.chm_work_unit_execution import validate_existing_hag_array, write_work_unit_diagnostic
from pyforestscan_qgis.core.empty_spatial_read import classify_empty_spatial_read
from pyforestscan_qgis.core.job_recovery import reconcile_polygon_job
from pyforestscan_qgis.core.source_aware_processing import AlignedRasterGrid, NativeSource, SourceAwareWorkPlan, SourceAwareWorkPlanner, SpatialExtent, WorkUnit, WorkUnitType
from pyforestscan_qgis.core.types import ChmRequest
from pyforestscan_qgis.core.work_unit_geometry import measure_core_polygon_intersection
from pyforestscan_qgis.core.work_unit_scheduler import CheckpointStore, PolygonProductWorkScheduler, WorkFailureCircuitBreaker, WorkUnitResult


class ExactGeometryTests(unittest.TestCase):
    def test_rectangle_and_boundary_only(self):
        extent=SpatialExtent(0,0,10,10)
        hit=measure_core_polygon_intersection(extent,'POLYGON ((5 0, 15 0, 15 10, 5 10, 5 0))')
        self.assertAlmostEqual(hit.intersection_area,50.0);self.assertAlmostEqual(hit.coverage_percent,50.0)
        touch=measure_core_polygon_intersection(extent,'POLYGON ((10 0, 20 0, 20 10, 10 10, 10 0))')
        self.assertFalse(touch.intersects);self.assertEqual(touch.intersection_area,0.0)

    def test_concave_multipolygon_hole_and_diagonal(self):
        extent=SpatialExtent(0,0,10,10)
        concave=measure_core_polygon_intersection(extent,'POLYGON ((0 0, 10 0, 10 2, 2 2, 2 10, 0 10, 0 0))')
        self.assertAlmostEqual(concave.intersection_area,36.0)
        multi=measure_core_polygon_intersection(extent,'MULTIPOLYGON (((0 0, 2 0, 2 2, 0 2, 0 0)), ((8 8, 10 8, 10 10, 8 10, 8 8)))')
        self.assertAlmostEqual(multi.intersection_area,8.0)
        hole=measure_core_polygon_intersection(extent,'POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0), (2 2, 8 2, 8 8, 2 8, 2 2))')
        self.assertAlmostEqual(hole.intersection_area,64.0)
        diagonal=measure_core_polygon_intersection(extent,'POLYGON ((0 0, 10 0, 0 10, 0 0))')
        self.assertAlmostEqual(diagonal.intersection_area,50.0)

    def test_tiny_positive_intersection_is_required(self):
        result=measure_core_polygon_intersection(SpatialExtent(0,0,10,10),'POLYGON ((9.999 9.999, 11 9.999, 11 11, 9.999 11, 9.999 9.999))')
        self.assertTrue(result.intersects);self.assertGreater(result.intersection_area,0)


class PlanningAndStatusTests(unittest.TestCase):
    def test_planner_filters_buffer_only_candidates(self):
        plan=SourceAwareWorkPlanner().plan(repository_kind='ept',sources=(NativeSource(Path('ept.json'),SpatialExtent(0,0,2000,1000)),),polygon_envelope=SpatialExtent(0,0,2000,1000),processing_crs='EPSG:26904',product='chm',resolution=1,polygon_wkt='POLYGON ((0 0, 975 0, 975 1000, 0 1000, 0 0))')
        self.assertGreaterEqual(plan.candidate_count,plan.required_count);self.assertEqual(plan.candidate_count,plan.required_count+plan.skipped_count)
        self.assertTrue(all(unit.polygon_intersection_area>0 for unit in plan.work_units))
        self.assertTrue(all(not unit.required_for_output for unit in plan.skipped_work_units))
        self.assertEqual(plan.skipped_count,1)
        self.assertTrue(plan.skipped_work_units[0].buffered_polygon_intersects)
        self.assertEqual(len(plan.plan_signature),64)

    def test_empty_read_semantics(self):
        self.assertEqual(classify_empty_spatial_read(core_intersection_area=0,source_coverage_expected=True,read_completed=True).status,'SkippedOutsidePolygon')
        self.assertEqual(classify_empty_spatial_read(core_intersection_area=1,source_coverage_expected=True,read_completed=True).status,'CompleteNoData')
        self.assertEqual(classify_empty_spatial_read(core_intersection_area=1,source_coverage_expected=True,read_completed=False,network_failure=True).status,'FailedEmptyRead')
        self.assertEqual(classify_empty_spatial_read(core_intersection_area=1,source_coverage_expected=None,read_completed=False).status,'NeedsCoverageReview')

    def test_breaker_only_trips_for_required_empty_failures(self):
        breaker=WorkFailureCircuitBreaker(pause_threshold=3,stop_threshold=5)
        for index in range(1,3):self.assertFalse(breaker.record(WorkUnitResult(f'wu-{index:04d}','Failed',error_code='FAILED_EMPTY_READ',message='same')).pause)
        decision=breaker.record(WorkUnitResult('wu-0003','Failed',error_code='FAILED_EMPTY_READ',message='same'))
        self.assertTrue(decision.pause);self.assertIn('required areas',decision.reason)
        separate=WorkFailureCircuitBreaker(pause_threshold=1)
        hag=separate.record(WorkUnitResult('wu-0001','Failed',error_code='HAG_METHOD_MISMATCH',message='same'))
        self.assertIn('height-normalization',hag.reason)


class DurabilityTests(unittest.TestCase):
    def _unit(self,index,required=True):
        core=SpatialExtent(index,0,index+1,1)
        return WorkUnit(f'wu-{index:04d}',WorkUnitType.EPT_WINDOW,(Path('ept.json'),),core,core,0,1,index,index+1,index,1,required_for_output=required,polygon_intersection_area=1.0 if required else 0.0)

    def test_disk_progress_and_geometry_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);units=tuple(self._unit(i,i not in {76,91,92,93}) for i in range(1,121));required=tuple(x for x in units if x.required_for_output);skipped=tuple(x for x in units if not x.required_for_output)
            grid=AlignedRasterGrid.from_extent(SpatialExtent(0,0,120,1),1,'EPSG:26904')
            plan=SourceAwareWorkPlan('ept','chm',grid,required,1,'Large','Moderate','sparse','none','durable',(),'remote',False,units,skipped)
            output=folder/'core.tif';output.write_bytes(b'ok')
            for i in range(1,91):
                path=folder/f'wu-{i:04d}'/'status.json';path.parent.mkdir(parents=True);path.write_text(json.dumps({'status':'Complete','output_path':str(output)}))
            summary=reconcile_polygon_job(folder,plan,'sig')
            self.assertEqual(summary.reclassified_outside,4);self.assertEqual(summary.recovered_complete,89);self.assertEqual(summary.pending_required,27);self.assertEqual(summary.failed_required,0)
            cached=CheckpointStore(folder,'sig').load_valid('wu-0001')
            self.assertIsNotNone(cached);self.assertEqual(cached.status,'Complete')
            counts=aggregate_work_unit_statuses(folder,120,116)
            self.assertEqual(counts['completed'],89);self.assertEqual(counts['skipped_outside_polygon'],4)
            self.assertNotEqual(counts['completed'],0)
            launched=[]
            def execute(unit,attempt):
                launched.append(unit.work_unit_id);output_path=folder/unit.work_unit_id/'core.tif';output_path.write_bytes(b'new')
                return WorkUnitResult(unit.work_unit_id,'Complete',output_path)
            results=PolygonProductWorkScheduler(plan.work_units,execute,CheckpointStore(folder,'sig'),concurrency=1,retry_count=0).run()
            self.assertEqual(launched,[f'wu-{index:04d}' for index in range(94,121)])
            self.assertTrue(all(item.status=='Complete' for item in results))

    def test_diagnostic_json_converts_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=write_work_unit_diagnostic(Path(tmp),'request.json',{'path':Path(tmp)/'x','items':(Path('a'),)})
            data=json.loads(path.read_text());self.assertIsInstance(data['path'],str);self.assertEqual(data['items'],['a'])

    def test_existing_hag_probe_is_shared_and_durable(self):
        try:import numpy
        except ImportError:self.skipTest('numpy unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            points=numpy.zeros(3,dtype=[('X','f8'),('Y','f8'),('HeightAboveGround','f8')]);points['HeightAboveGround']=[0,2,5]
            request=ChmRequest(Path('ept.json'),Path(tmp)/'out.tif',1,'EPSG:26904',hag_method='existing_normalized_height',diagnostics_path=Path(tmp)/'diagnostics')
            stats=validate_existing_hag_array(points,request)
            self.assertEqual(stats['maximum'],5.0);self.assertTrue((Path(tmp)/'diagnostics'/'point_statistics.json').is_file())
            self.assertTrue((Path(tmp)/'diagnostics'/'source_schema.json').is_file())
            self.assertTrue((Path(tmp)/'diagnostics'/'hag_execution_decision.json').is_file())


if __name__=='__main__':unittest.main()
