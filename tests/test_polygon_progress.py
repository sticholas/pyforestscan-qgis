"""Regression tests for determinate Polygon Area progress."""

from __future__ import annotations

import unittest

from pyforestscan_qgis.core.polygon_progress import PolygonProgressProjection, progress_event


class PolygonProgressProjectionTests(unittest.TestCase):
    def test_stage_only_event_has_determinate_percentage(self) -> None:
        projection = PolygonProgressProjection(total_datasets=2, total_products=3)
        event = progress_event(attempt_id="a", sequence=1, event_type="STAGE", stage="PREPARING", entity_type="dataset", entity_id="tile.las")
        self.assertTrue(projection.apply(event))
        self.assertEqual(8, projection.progress_percent(event))

    def test_product_completion_advances_without_worker_percentage(self) -> None:
        projection = PolygonProgressProjection(total_datasets=1, total_products=2)
        event = progress_event(attempt_id="a", sequence=1, event_type="PRODUCT", stage="GENERATING", entity_type="product", entity_id="tile:chm", state="SUCCEEDED")
        projection.apply(event)
        self.assertEqual(67, projection.progress_percent(event))

    def test_precise_worker_percentage_is_preserved_and_capped_before_finish(self) -> None:
        projection = PolygonProgressProjection(total_datasets=1, total_products=1)
        event = progress_event(attempt_id="a", sequence=1, event_type="PROGRESS", stage="GENERATING", entity_type="product", entity_id="tile:chm", progress_percent=100)
        projection.apply(event)
        self.assertEqual(99, projection.progress_percent(event))


if __name__ == "__main__":
    unittest.main()
