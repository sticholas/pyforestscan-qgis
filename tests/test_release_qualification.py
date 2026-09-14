"""Contracts for the repeatable release qualification inventory."""

from __future__ import annotations

import unittest

from scripts.qualify_release import inventory_provider


class ReleaseQualificationInventoryTests(unittest.TestCase):
    def test_provider_inventory_matches_registered_manifest(self) -> None:
        rows = inventory_provider()
        self.assertEqual(len(rows), 14)
        ids = [str(row["feature_id"]) for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("advanced_chm", ids)
        self.assertIn("advanced_dtm", ids)
        self.assertIn("advanced_voxel_statistic", ids)
        for row in rows:
            for field in ("feature_id", "display_name", "module", "public_surface", "status", "qgis_runtime_status"):
                self.assertTrue(row[field], f"missing {field}: {row}")


if __name__ == "__main__":
    unittest.main()
