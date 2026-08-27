import json
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.models import BackendPlatform
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.processing_engine import (
    ProcessingEngineError,
    ProcessingEngineReport,
    ProcessingEngineService,
    ProcessingEngineState,
    PROCESSING_ENGINE_CONTRACT_VERSION,
    current_plugin_build_id,
    current_runner_hash,
    contract_hash,
    dependency_manifest_hash,
    environment_fingerprint,
    product_capability_hash,
    processing_engine_manifest_path,
)
from pyforestscan_qgis.core.backend.runtime_manifest import PRODUCT_CAPABILITIES
from pyforestscan_qgis.core.lidar_inventory import LidarSourceRecord
from pyforestscan_qgis.core.polygon_batch import validate_polygon_execution_manifest
from pyforestscan_qgis.core.source_alternatives import SourceRelationship, canonicalize_source_alternatives
from pyforestscan_qgis.core.source_aware_processing import NativeSource, SourceAwareWorkPlanner, SpatialExtent
from pyforestscan_qgis.core.spatial_selection import Bounds2D


class RuntimeHandoffTests(unittest.TestCase):
    def _service(self, folder):
        paths = resolve_backend_paths(Path(folder), BackendPlatform.WINDOWS)
        paths.python_executable.parent.mkdir(parents=True)
        paths.python_executable.touch()
        service = ProcessingEngineService(paths)
        contract = {
            "python_executable": str(paths.python_executable),
            "environment_fingerprint": environment_fingerprint(paths),
            "protocol_version": "2",
            "runner_sha256": current_runner_hash(),
            "plugin_build_id": current_plugin_build_id(),
            "dependency_manifest_hash": dependency_manifest_hash(),
            "product_capability_hash": product_capability_hash(tuple(PRODUCT_CAPABILITIES)),
            "engine_id": "engine-a",
            "verified_at": "2026-08-27T00:00:00Z",
            "versions": {"pyforestscan": "0.4.1"},
            "contract_version": PROCESSING_ENGINE_CONTRACT_VERSION,
            "setup_completed_at": "2026-08-27T00:00:00Z",
            "setup_plugin_build_id": current_plugin_build_id(),
            "status": ProcessingEngineState.READY.value,
        }
        contract["runner_hash"] = contract["runner_sha256"]
        contract["contract_hash"] = contract_hash(contract)
        processing_engine_manifest_path(paths).write_text(json.dumps(contract), encoding="utf-8")
        service.state(quick=True)
        return service

    def test_prerun_token_is_accepted_without_new_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self._service(folder)
            token = service.runtime_token_for(("chm", "rumple"))
            comparison = service.validate_runtime_token_for_launch(token, ("chm", "rumple"), Path(folder))
            self.assertTrue(all(item["status"] == "MATCH" for item in comparison.values()))
            self.assertTrue((Path(folder) / "runtime_token_comparison.json").exists())

    def test_old_token_after_repair_reports_exact_field(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self._service(folder)
            old = service.runtime_token_for(("chm", "rumple"))
            manifest_path = processing_engine_manifest_path(service.paths)
            contract = json.loads(manifest_path.read_text(encoding="utf-8"))
            contract["setup_completed_at"] = "2026-08-27T01:00:00Z"
            contract["contract_hash"] = contract_hash(contract)
            manifest_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(ProcessingEngineError) as raised:
                service.validate_runtime_token_for_launch(old, ("chm", "rumple"))
            self.assertEqual(raised.exception.code, "ENGINE_RUNTIME_TOKEN_MISMATCH")
            self.assertIn("contract_hash", raised.exception.technical_message)

    def test_manifest_requires_frozen_runtime_and_unique_work_units(self):
        payload = {
            "processing_runtime": {field: "x" for field in ("engine_id", "executable", "environment_fingerprint", "contract_hash", "protocol", "backend_runner_hash", "dependency_manifest_hash", "product_capability_hash", "plugin_build_id")},
            "selected_source_paths": ["normalized.las"],
            "plan_signature": "plan",
            "execution_plan": {"products": ["chm", "rumple"], "polygon_context": {"processing_geometry": "POLYGON (...)"}},
            "source_aware_raster_plan": {"work_units": [{"work_unit_id": "wu-a-0001"}, {"work_unit_id": "wu-a-0002"}]},
        }
        validate_polygon_execution_manifest(payload)
        payload["source_aware_raster_plan"]["work_units"][1]["work_unit_id"] = "wu-a-0001"
        with self.assertRaisesRegex(ValueError, "unique_work_unit_id"):
            validate_polygon_execution_manifest(payload)

    def test_polygon_launch_has_no_independent_verifier_or_token_resolver(self):
        root = Path(__file__).parents[1]
        polygon = (root / "pyforestscan_qgis/core/polygon_batch.py").read_text(encoding="utf-8")
        execution = (root / "pyforestscan_qgis/core/backend/execution.py").read_text(encoding="utf-8")
        pages = (root / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")
        self.assertNotIn("ProcessingEngineVerifier(BackendService().paths)", polygon)
        self.assertNotIn("ProcessingEngineVerifier(BackendService().paths)", pages)
        submit = execution[execution.index("def submit_polygon_coordinator"):execution.index("def run_product", execution.index("def submit_polygon_coordinator"))]
        self.assertIn("runtime_token: ProcessingRuntimeToken", submit)
        self.assertNotIn(".runtime_token_for(", submit)


class SourceIdentityTests(unittest.TestCase):
    def _real_shape(self):
        bounds = Bounds2D(271368.874, 2152762.757, 272118.751, 2153464.879)
        raw = LidarSourceRecord(Path("OlaaFR_RoadSite_Heli_Thin05_CropPC.las"), "las", 3773506491, 1, bounds, "EPSG:6635", 104819538, 813.179, 870.024)
        normalized = LidarSourceRecord(Path("OlaaFR_RoadSite_Heli_Thin05_CropPC_Norm.las"), "las", 3773503743, 2, bounds, "EPSG:6635", 104819538, -7.078, 23.643)
        return raw, normalized

    def test_real_raw_normalized_shape_selects_one_canonical_source(self):
        raw, normalized = self._real_shape()
        selected, detections = canonicalize_source_alternatives((raw, normalized))
        self.assertEqual(selected, (normalized,))
        self.assertEqual(detections[0].relationship, SourceRelationship.POTENTIAL_ALTERNATIVE_REPRESENTATION)
        self.assertEqual(sum(item.point_count or 0 for item in selected), 104819538)

    def test_two_large_sources_have_global_checkpoint_ids(self):
        raw, normalized = self._real_shape()
        extent = SpatialExtent(271370.8157, 2152764.5732, 272114.8157, 2153463.5732)
        sources = tuple(NativeSource(item.path, SpatialExtent(item.bounds.xmin, item.bounds.ymin, item.bounds.xmax, item.bounds.ymax), item.size_bytes, item.point_count, "las") for item in (raw, normalized))
        plan = SourceAwareWorkPlanner().plan(repository_kind="folder", sources=sources, polygon_envelope=extent, processing_crs="EPSG:6635", product="chm", resolution=1.0, available_memory_bytes=8 * 1024**3, cpu_count=4)
        ids = [item.work_unit_id for item in plan.candidate_work_units]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item.startswith("wu-") and len(item.split("-")) == 3 for item in ids))


if __name__ == "__main__":
    unittest.main()
