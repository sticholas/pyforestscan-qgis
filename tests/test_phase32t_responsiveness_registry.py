"""Phase 32T responsiveness and scientific registry contracts."""
from pathlib import Path
import unittest

from pyforestscan_qgis.core.product_registry import CALCULATE_FUNCTION_CLASSIFICATIONS, MISSION_CONTROL_PRODUCTS, PRODUCT_BY_TYPE
from pyforestscan_qgis.core.batch import BatchProductSettings
from pyforestscan_qgis.core.pipeline_context import PipelineContext
from pyforestscan_qgis.core.product_plan import ProductPlannerReport, plan_to_dict
from pyforestscan_qgis.core.types import ProductType


ROOT = Path(__file__).resolve().parents[1]
PAGES = (ROOT / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")


class Phase32TRegistryTests(unittest.TestCase):
    def test_release_product_surface_is_explicit(self) -> None:
        self.assertEqual(
            (ProductType.CHM, ProductType.DTM, ProductType.PAD, ProductType.PAI, ProductType.FHD,
             ProductType.CANOPY_COVER, ProductType.RUMPLE, ProductType.POINT_DENSITY),
            tuple(item.product for item in MISSION_CONTROL_PRODUCTS),
        )
        self.assertEqual("advanced_operation", PRODUCT_BY_TYPE[ProductType.VOXEL_STAT].classification)

    def test_official_defaults_are_release_pinned(self) -> None:
        fhd = {item.key: item.default for item in PRODUCT_BY_TYPE[ProductType.FHD].parameters}
        cover = {item.key: item.default for item in PRODUCT_BY_TYPE[ProductType.CANOPY_COVER].parameters}
        self.assertEqual({"voxel_height": 1.0, "min_height": 0.0, "max_height": None}, fhd)
        self.assertEqual(2.0, cover["min_height"])
        self.assertEqual(0.5, cover["k"])
        settings = BatchProductSettings((ProductType.CHM,), 1.0)
        self.assertEqual(0.0, settings.fhd_min_height)
        self.assertEqual(1.0, settings.pai_min_height)
        self.assertTrue(settings.point_density_per_area)

    def test_official_calculate_inventory_is_classified(self) -> None:
        self.assertEqual(10, len(CALCULATE_FUNCTION_CLASSIFICATIONS))
        self.assertEqual("internal_primitive", CALCULATE_FUNCTION_CLASSIFICATIONS["assign_voxels"])
        self.assertEqual("advanced_operation", CALCULATE_FUNCTION_CLASSIFICATIONS["calculate_voxel_stat"])

    def test_product_toggle_path_never_normalizes_polygon(self) -> None:
        callback = PAGES[PAGES.index("def _on_product_selection_changed"):PAGES.index("def _publish_session_state")]
        self.assertNotIn("_normalized_polygon_selection", callback)
        self.assertNotIn("refresh_catalog_status", callback)
        self.assertNotIn("_refresh_footprint_label", callback)
        self.assertNotIn("_on_session_input_changed)", PAGES[PAGES.index("for check in self.product_checks.values():", PAGES.index("def _wire_session_state_inputs")):PAGES.index("self.polygon_lidar_folder_edit.textChanged")])

    def test_each_product_has_unique_context_help(self) -> None:
        descriptions = [item.description for item in MISSION_CONTROL_PRODUCTS]
        self.assertEqual(len(descriptions), len(set(descriptions)))
        self.assertTrue(all(description.endswith(".") for description in descriptions))

    def test_responsive_workspace_preserves_vertical_workflow(self) -> None:
        self.assertIn('columns = 4 if width >= 720 else 2', PAGES)
        self.assertIn('setObjectName("responsiveProcessWorkspace")', PAGES)
        self.assertIn('self.process_workspace_layout = QVBoxLayout', PAGES)
        self.assertNotIn('self.process_workspace_layout = QGridLayout', PAGES)
        mode_change = PAGES[PAGES.index("def _update_batch_mode_visibility"):PAGES.index("def _on_execution_mode_changed")]
        self.assertNotIn("refresh_catalog_status", mode_change)

    def test_scientific_parameters_survive_product_plan_serialization(self) -> None:
        report = ProductPlannerReport(
            title="test", generated_at="now", source_report=Path("report.json"),
            source_dataset="input.laz", output_folder=Path("outputs"), grid_resolution=2.0,
            height_bin_size=0.5, chm_interpolation="linear",
            chm_interpolate_valid_region=False, chm_clean_edges=False,
            chm_output_filename="chm.tif", pad_output_filename="pad.tif",
            pai_output_filename="pai.tif", fhd_output_filename="fhd.tif",
            rumple_output_filename="rumple.tif", canopy_cover_height_threshold=3.0,
            canopy_cover_max_height=40.0, canopy_cover_extinction_coefficient=0.6,
            pad_beer_lambert_constant=1.2, pad_drop_ground=False,
            pai_min_height=1.5, pai_max_height=35.0,
            fhd_min_height=0.5, fhd_max_height=38.0, rumple_min_height=2.0,
            canopy_cover_output_filename="cover.tif", notes="", estimated_columns=None,
            estimated_rows=None, estimated_cells=None, estimated_height_bins=None,
            products=(), warnings=(), next_actions=(),
        )
        payload = plan_to_dict(report)
        context = PipelineContext("fhd", "FHD", Path("plan.json"), Path("outputs"), payload, {})
        self.assertEqual(0.5, context.fhd_min_height)
        self.assertEqual(38.0, context.fhd_max_height)
        self.assertEqual(1.2, context.pad_beer_lambert_constant)
        self.assertEqual(0.6, context.canopy_cover_extinction_coefficient)
        self.assertEqual(2.0, context.rumple_min_height)


if __name__ == "__main__":
    unittest.main()
