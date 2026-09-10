"""QGIS-free tests for explicit object-ID semantics and bounded allocation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from pyforestscan_qgis.core.point_cloud.object_catalog import build_object_catalog
from pyforestscan_qgis.core.point_cloud.object_id_policy import (
    ObjectIdPolicy, create_object_id_policy, next_available_object_id,
    object_id_policy_summary)


@unittest.skipIf(np is None, "numpy unavailable")
class ObjectIdPolicyTests(unittest.TestCase):
    SHA = "c" * 64

    def catalog(self, folder, ids, dtype="i2"):
        values = np.zeros(len(ids), dtype=[("X","f8"),("Y","f8"),("Z","f8"),("Tree_ID",dtype)])
        values["X"] = np.arange(len(ids))
        values["Y"] = np.arange(len(ids))
        values["Z"] = np.arange(len(ids))
        values["Tree_ID"] = ids
        return build_object_catalog((values,), len(values), "Tree_ID",
                                    Path(folder)/"objects.sqlite", self.SHA)

    def test_policy_uses_real_integer_storage_range_and_explicit_unassigned_value(self):
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [1,2,4], "i2")
            policy = create_object_id_policy(report, 0)
            self.assertEqual((policy.storage_minimum, policy.storage_maximum), (-32768,32767))
            self.assertEqual(policy.unassigned_id, 0)
            self.assertEqual(policy.semantics, "USER_CONFIRMED_UNASSIGNED_VALUE")
            self.assertIn("Unassigned = 0", object_id_policy_summary(policy, 3))
            self.assertTrue(report["editable_integer_ids"])

    def test_next_id_finds_first_gap_without_loading_catalog(self):
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [1,1,2,4,4], "u2")
            policy = create_object_id_policy(report, 0)
            self.assertEqual(next_available_object_id(report["catalog_path"], policy), 3)
            self.assertEqual(next_available_object_id(report["catalog_path"], policy,
                                                      preferred_start=4), 5)

    def test_unassigned_value_is_never_allocated_and_overflow_is_explicit(self):
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [1,2], "u1")
            policy = create_object_id_policy(report, 3)
            self.assertEqual(next_available_object_id(report["catalog_path"], policy), 4)
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [254], "u1")
            policy = create_object_id_policy(report, 255)
            with self.assertRaisesRegex(OverflowError, "No object ID"):
                next_available_object_id(report["catalog_path"], policy, preferred_start=254)

    def test_float_fields_remain_read_only_and_range_is_validated(self):
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [1,1,2], "f4")
            self.assertFalse(report["editable_integer_ids"])
            with self.assertRaisesRegex(ValueError, "remains read-only"):
                create_object_id_policy(report, 0)
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [1,2], "u1")
            with self.assertRaisesRegex(ValueError, "storage range"):
                create_object_id_policy(report, -1)

    def test_policy_must_match_exact_source_field_and_dtype(self):
        with TemporaryDirectory() as folder:
            report = self.catalog(folder, [1,2], "i2")
            policy = create_object_id_policy(report, 0)
            incompatible = ObjectIdPolicy("d"*64, policy.field, policy.field_dtype,
                policy.storage_minimum, policy.storage_maximum, policy.unassigned_id)
            with self.assertRaisesRegex(ValueError, "does not belong"):
                next_available_object_id(report["catalog_path"], incompatible)
            wrong_range = ObjectIdPolicy(policy.source_sha256, policy.field, policy.field_dtype,
                policy.storage_minimum, policy.storage_maximum + 1, policy.unassigned_id)
            with self.assertRaisesRegex(ValueError, "storage range does not match"):
                next_available_object_id(report["catalog_path"], wrong_range)

    def test_worker_persists_confirmed_policy_without_staging_an_edit(self):
        worker = (Path(__file__).parents[1] / "pyforestscan_qgis" / "viewer" /
                  "editor_worker.py").read_text(encoding="utf-8")
        self.assertIn('elif action == "configure_object_id_policy":', worker)
        self.assertIn('session.visibility["object_id_policy"] = {', worker)
        self.assertNotIn('stage_resolved(definitions, result, field', worker)
