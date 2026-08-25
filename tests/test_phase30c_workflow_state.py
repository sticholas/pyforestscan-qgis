"""Phase 30C processing-state and Advanced-control regressions."""

from __future__ import annotations

import tempfile
import unittest
import ast
from dataclasses import replace
from pathlib import Path

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_control_visibility import batch_control_visibility
from pyforestscan_qgis.core.batch_execution_contract import prepare_batch_execution
from pyforestscan_qgis.core.batch_preflight import BatchPreflightReport
from pyforestscan_qgis.core.types import ProductType


ROOT = Path(__file__).resolve().parents[1]


def report(root: Path, selected: tuple[Path, ...], skipped: tuple[Path, ...] = ()) -> BatchPreflightReport:
    return BatchPreflightReport(root / "batch", True, (), (), 0, 10**9, selected, (), skipped, (), root / "batch" / "manifest.json", "parallel_safe", 4, 1)


class BatchExecutionContractTests(unittest.TestCase):
    def test_single_las_chm_rumple_without_persisted_ui_preflight(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "plot.las"
            source.touch()
            settings = BatchProductSettings((ProductType.CHM, ProductType.RUMPLE), 1.0, execution_mode="parallel_safe", max_workers=4, load_outputs_into_qgis=True, confirm_large_parallel=True)
            request = BatchRequest(root, root / "out", False, (source,), settings)
            launch = prepare_batch_execution(request, report(root, (source,)), profile="Automatic (Recommended)")
            self.assertEqual((source,), launch.request.datasets)
            self.assertEqual(("chm", "rumple"), launch.readiness.products)
            self.assertEqual(1, launch.logical_inputs)
            self.assertEqual(0, launch.sources_skipped)
            self.assertEqual(4, launch.readiness.requested_concurrency_limit)

    def test_skipped_sources_do_not_inflate_processing_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            selected, skipped = root / "a.laz", root / "done.las"
            settings = BatchProductSettings((ProductType.CHM,), 1.0)
            request = BatchRequest(root, root / "out", False, (selected, skipped), settings)
            launch = prepare_batch_execution(request, report(root, (selected,), (skipped,)))
            self.assertEqual(1, launch.logical_inputs)
            self.assertEqual(1, launch.sources_skipped)

    def test_execution_defining_change_produces_new_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.copc.laz"
            settings = BatchProductSettings((ProductType.CHM,), 1.0)
            request = BatchRequest(root, root / "out", False, (source,), settings)
            first = prepare_batch_execution(request, report(root, (source,)))
            second = prepare_batch_execution(replace(request, settings=replace(settings, grid_resolution=2.0)), report(root, (source,)))
            self.assertNotEqual(first.readiness.plan_identity, second.readiness.plan_identity)

    def test_supported_standard_source_shapes_share_one_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = BatchProductSettings((ProductType.CHM,), 1.0)
            for names in (("one.las",), ("a.las", "b.laz"), ("cloud.copc.laz",), ("ept.json",)):
                with self.subTest(names=names):
                    sources = tuple(root / name for name in names)
                    request = BatchRequest(root, root / "out", True, sources, settings)
                    launch = prepare_batch_execution(request, report(root, sources))
                    self.assertEqual(sources, launch.request.datasets)
                    self.assertEqual(len(sources), launch.logical_inputs)

    def test_four_consecutive_requests_have_distinct_current_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            launches = []
            cases = (
                ((root / "a.las",), (ProductType.CHM,)),
                ((root / "a.las",), (ProductType.CHM, ProductType.RUMPLE)),
                ((root / "a.las", root / "b.laz"), (ProductType.CHM,)),
                ((root / "ept.json",), (ProductType.RUMPLE,)),
            )
            for sources, products in cases:
                settings = BatchProductSettings(products, 1.0)
                request = BatchRequest(root, root / "out", True, sources, settings)
                launches.append(prepare_batch_execution(request, report(root, sources)))
            self.assertEqual(4, len({item.readiness.plan_identity for item in launches}))
            self.assertEqual(("rumple",), launches[-1].readiness.products)


class AdvancedVisibilityTests(unittest.TestCase):
    def test_visibility_is_idempotent_for_one_hundred_transitions(self):
        baseline = batch_control_visibility(profile="recommended", execution_mode="parallel_safe", polygon_mode=False, repository_selected=False)
        states = []
        for index in range(100):
            custom = index % 4 in {1, 2}
            state = batch_control_visibility(
                profile="custom" if custom else "recommended",
                execution_mode="parallel_safe" if index % 3 else "sequential",
                polygon_mode=bool(index % 2),
                repository_selected=bool(index % 5),
            )
            states.append(state)
        self.assertEqual(baseline, batch_control_visibility(profile="recommended", execution_mode="parallel_safe", polygon_mode=False, repository_selected=False))
        self.assertTrue(any(item.maximum_workers for item in states))
        self.assertTrue(all(not item.parallel_confirmation for item in states))

    def test_custom_profile_is_only_worker_ceiling_override_state(self):
        automatic = batch_control_visibility(profile="recommended", execution_mode="parallel_safe", polygon_mode=False, repository_selected=False)
        sequential = batch_control_visibility(profile="custom", execution_mode="sequential", polygon_mode=False, repository_selected=False)
        parallel = batch_control_visibility(profile="custom", execution_mode="parallel_safe", polygon_mode=False, repository_selected=False)
        self.assertFalse(automatic.execution_mode)
        self.assertFalse(sequential.execution_mode)
        self.assertTrue(sequential.maximum_workers)
        self.assertTrue(parallel.maximum_workers)


class StaticBatchPageRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

    def test_launch_does_not_dereference_mutable_preflight_after_queue_updates(self):
        run = self.source.split("    def run_batch", 1)[1].split("    def _run_polygon_batch", 1)[0]
        self.assertIn("execution = prepare_batch_execution", run)
        self.assertIn("execution.logical_inputs", run)
        self.assertNotIn("self.preflight_report.files_to_skip", run)

    def test_programmatic_file_status_updates_do_not_invalidate_readiness(self):
        queued = self.source.split("    def _mark_selected_files_queued", 1)[1].split("    def _update_file_row", 1)[0]
        self.assertIn("self.file_list.blockSignals(True)", queued)
        self.assertIn("self.file_list.blockSignals(blocked)", queued)

    def test_collapsible_container_preserves_child_semantic_visibility(self):
        helper = self.source.split("def _collapsible_section", 1)[1].split("def _set_layout_visible", 1)[0]
        self.assertIn("group._content_widget = content", helper)
        self.assertNotIn("_set_layout_visible(child_layout", helper)
        self.assertIn("self.execution_mode_container = QWidget()", self.source)
        self.assertIn("self.max_workers_container = QWidget()", self.source)

    def test_private_batch_page_calls_resolve_or_are_injected(self):
        tree = ast.parse(self.source)
        batch = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BatchPage")
        methods = {node.name for node in batch.body if isinstance(node, ast.FunctionDef)}
        calls = {
            node.func.attr
            for node in ast.walk(batch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr.startswith("_")
        }
        self.assertEqual({"_job_token_factory"}, calls - methods)


if __name__ == "__main__":
    unittest.main()
