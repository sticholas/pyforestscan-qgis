import unittest

from pyforestscan_qgis.core.point_cloud.analytics_scheduler import (
    AnalyticsCoalescer, BoundedAnalyticsCache)


class AnalyticsSchedulerTests(unittest.TestCase):
    def test_rapid_submits_keep_only_latest_pending_request(self):
        gate = AnalyticsCoalescer()
        for index in range(100):
            gate.submit(("profile", index), index)
        request = gate.take_latest()
        self.assertEqual(99, request.payload)
        self.assertIsNone(gate.pending)
        self.assertTrue(gate.is_current(request))

    def test_out_of_order_results_cannot_replace_newest(self):
        gate = AnalyticsCoalescer()
        first = gate.submit(("view",), "A")
        second = gate.submit(("view",), "B")
        self.assertFalse(gate.finish(first))
        self.assertTrue(gate.finish(second))

    def test_cache_is_bounded_and_reuses_entries(self):
        cache = BoundedAnalyticsCache(2)
        cache.put((1,), "one")
        cache.put((2,), "two")
        self.assertEqual("one", cache.get((1,)))
        cache.put((3,), "three")
        self.assertIsNone(cache.get((2,)))
        self.assertEqual(2, len(cache))


if __name__ == "__main__":
    unittest.main()
