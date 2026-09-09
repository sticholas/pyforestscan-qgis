"""QGIS-free tests for preparation ordering and immutable array handling."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.lidar_preparation import HeightNormalizationPlanMode as Mode
from pyforestscan_qgis.core.point_cloud.preparation import PreparationOptions
from pyforestscan_qgis.core.point_cloud.preparation_execution import prepare_arrays

MODULE = "pyforestscan_qgis.core.point_cloud.preparation_execution"


@unittest.skipIf(np is None, "NumPy is required for structured-array contract tests")
class PreparationExecutionTests(unittest.TestCase):
    def setUp(self):
        self.source = np.array([(1, 2, 100, 0), (3, 4, 110, 10)],
            dtype=[("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("HeightAboveGround", "f8")])
        self.filters = Mock()
        self.context = dict(filters_module=self.filters, assessment=object(),
            plan=SimpleNamespace(height_mode=Mode.USE_EXISTING_HAG, can_execute=True),
            run_folder=Path("unused"), job_identity="test")

    def execute(self, options, **kwargs):
        return prepare_arrays((self.source,), options, **{**self.context, **kwargs})

    def fake_height(self, arrays, *args, **kwargs):
        return SimpleNamespace(arrays=arrays, provenance_path=Path("height.json"))

    def test_voxel_uses_first_and_does_not_mutate_caller(self):
        before = self.source.copy()
        def thin(arrays, spacing, mode):
            self.assertEqual((spacing, mode), (.5, "first"))
            return (arrays[0][:1],)
        self.filters.downsample_voxel.side_effect = thin
        result = self.execute(PreparationOptions(thinning="voxel_first", spacing=.5))
        np.testing.assert_array_equal(self.source, before)
        self.assertEqual((result.input_points, result.output_points), (2, 1))
        self.assertNotIn("PFSPreparationRecordId", result.arrays[0].dtype.names)

    def test_filter_attribute_mutation_fails_without_mutating_source(self):
        before = self.source.copy()
        def bad_filter(arrays, spacing):
            arrays[0]["X"] = 9
            return arrays
        self.filters.downsample_poisson.side_effect = bad_filter
        with self.assertRaisesRegex(ValueError, "dimension X"):
            self.execute(PreparationOptions(thinning="poisson", spacing=1))
        np.testing.assert_array_equal(self.source, before)

    def test_duplicate_retained_record_fails(self):
        self.filters.downsample_poisson.side_effect = lambda arrays, spacing: (arrays[0][[0, 0]],)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.execute(PreparationOptions(thinning="poisson", spacing=1))

    @patch(MODULE + ".execute_preparation")
    def test_thinning_cannot_change_normalized_height(self, height):
        height.side_effect = self.fake_height
        def corrupt(arrays, spacing):
            arrays[0]["Z"] = 123
            return arrays
        self.filters.downsample_poisson.side_effect = corrupt
        with self.assertRaisesRegex(ValueError, "dimension Z"):
            self.execute(PreparationOptions(
                thinning="poisson", spacing=1, height_action="normalize_z"))

    def test_lost_identity_fails(self):
        self.filters.downsample_poisson.return_value = (self.source.copy(),)
        with self.assertRaisesRegex(ValueError, "identities"):
            self.execute(PreparationOptions(thinning="poisson", spacing=1))

    @patch(MODULE + ".execute_preparation")
    def test_normalize_retains_original_z_before_thinning(self, height):
        height.side_effect = self.fake_height
        def thin(arrays, spacing):
            np.testing.assert_array_equal(arrays[0]["Z"], [0, 10])
            np.testing.assert_array_equal(arrays[0]["PFSOriginalZ"], [100, 110])
            return (arrays[0][1:],)
        self.filters.downsample_poisson.side_effect = thin
        result = self.execute(PreparationOptions(
            thinning="poisson", spacing=1, height_action="normalize_z"))
        self.assertEqual(result.output_points, 1)
        self.assertEqual(result.height_provenance, "height.json")
        np.testing.assert_array_equal(self.source["Z"], [100, 110])

    @patch(MODULE + ".execute_preparation")
    def test_add_hag_keeps_z(self, height):
        height.side_effect = self.fake_height
        result = self.execute(PreparationOptions(height_action="add_hag"))
        np.testing.assert_array_equal(result.arrays[0]["Z"], self.source["Z"])
        self.assertNotIn("PFSOriginalZ", result.arrays[0].dtype.names)

    @patch(MODULE + ".execute_preparation")
    def test_ground_classification_requires_consent(self, height):
        self.context["plan"].height_mode = Mode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY
        with self.assertRaisesRegex(ValueError, "consent"):
            self.execute(PreparationOptions(height_action="add_hag"))
        height.assert_not_called()
        height.side_effect = self.fake_height
        self.execute(PreparationOptions(height_action="add_hag", allow_ground_classification=True))
        height.assert_called_once()

    def test_unqualified_height_mode_is_rejected(self):
        self.context["plan"].height_mode = Mode.EXISTING_NORMALIZED_Z
        with self.assertRaisesRegex(ValueError, "not executable"):
            self.execute(PreparationOptions(height_action="normalize_z"))

    @patch(MODULE + ".execute_preparation")
    def test_nonfinite_hag_cannot_become_z(self, height):
        self.source["HeightAboveGround"][0] = np.nan
        height.side_effect = self.fake_height
        with self.assertRaisesRegex(ValueError, "finite HAG"):
            self.execute(PreparationOptions(height_action="normalize_z"))

    def test_existing_original_z_is_not_overwritten(self):
        from numpy.lib.recfunctions import append_fields
        self.source = append_fields(self.source, "PFSOriginalZ", [8., 9.], usemask=False)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.execute(PreparationOptions(height_action="normalize_z"))

    def test_cancel_before_filters(self):
        with self.assertRaises(InterruptedError):
            self.execute(PreparationOptions(thinning="poisson", spacing=1), cancelled=lambda: True)
        self.filters.downsample_poisson.assert_not_called()

    def test_qgis_scientific_boundary(self):
        with patch(MODULE + ".assert_scientific_import_allowed", side_effect=RuntimeError("boundary")):
            with self.assertRaisesRegex(RuntimeError, "boundary"):
                self.execute(PreparationOptions(thinning="poisson", spacing=1))

    def test_empty_filter_result_fails(self):
        self.filters.downsample_poisson.return_value = (self.source[:0],)
        with self.assertRaisesRegex(ValueError, "point count"):
            self.execute(PreparationOptions(thinning="poisson", spacing=1))
