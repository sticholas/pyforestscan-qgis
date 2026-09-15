"""Static contract checks for the QGIS point-cloud stress harness."""
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "qgis_point_cloud_viewer_stress.py"


class PointCloudViewerStressContractTests(unittest.TestCase):
    def test_harness_requires_the_full_fifty_cycle_gate(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('default=50', source)
        self.assertIn('args.cycles < 50', source)
        self.assertIn('for cycle in range(1, cycles + 1)', source)

    def test_harness_covers_the_three_linked_views(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for marker in ("page.overview_id", "ViewType.AREA_DETAIL", "ViewType.VERTICAL_SLICE",
                       "open_linked_view", "page.linked.rendered_id"):
            self.assertIn(marker, source)

    def test_harness_records_sizing_and_lifecycle_invariants(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for marker in ("surface", "tabs", "worker_count", "renderer_owner_count",
                       "resident_count", "sizeHint"):
            self.assertIn(marker, source)
        self.assertIn("width >= 180 and height >= 180", source)
        self.assertIn('renderer_owner_count"] <= 1', source)


if __name__ == "__main__":
    unittest.main()
