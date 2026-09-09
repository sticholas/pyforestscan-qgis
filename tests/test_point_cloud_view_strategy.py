"""QGIS-free intake and cache lifecycle regressions."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from pyforestscan_qgis.core.point_cloud.view_strategy import (
    CacheState, PointCloudViewStrategyPlanner, SourceViewFacts, ViewStrategy,
    cache_identity, cache_key, session_cache_hint,
)
from pyforestscan_qgis.core.point_cloud.view_cache import ViewCache


def source(**kwargs):
    return replace(SourceViewFacts("LAZ", 1_000_000, 20_000,
                   dimensions=("X", "Y", "Z", "Classification", "HeightAboveGround"),
                   crs="EPSG:32605", fingerprint="a" * 64, modified_ns=123), **kwargs)


class ViewStrategyTests(unittest.TestCase):
    def test_native_paths_do_not_require_cache_or_hash(self):
        planner = PointCloudViewStrategyPlanner()
        for fmt, expected in (("COPC", ViewStrategy.COPC_NATIVE), ("EPT", ViewStrategy.EPT_NATIVE)):
            self.assertEqual(planner.plan(source(source_format=fmt, fingerprint="",
                             point_count=110_008_858_527)).strategy, expected)

    def test_no_implicit_unimplemented_direct_path(self):
        self.assertEqual(PointCloudViewStrategyPlanner().plan(source()).strategy,
                         ViewStrategy.BUILD_VIEW_CACHE)

    def test_small_enabled_direct_path(self):
        plan = PointCloudViewStrategyPlanner(direct_available=True).plan(source())
        self.assertEqual(plan.strategy, ViewStrategy.DIRECT)
        self.assertTrue(plan.original_is_authority)
        self.assertFalse(plan.threshold_qualified)

    def test_all_larger_sources_automatically_choose_cache(self):
        planner = PointCloudViewStrategyPlanner(direct_available=True)
        for count in (500_000, 2_287_408, 5_000_000, 10_000_000, 50_000_000,
                      104_819_538, 1_000_000_000):
            self.assertEqual(planner.plan(source(point_count=count)).strategy,
                             ViewStrategy.BUILD_VIEW_CACHE)

    def test_memory_pressure_and_record_size_win(self):
        planner = PointCloudViewStrategyPlanner(direct_available=True)
        for facts in (source(available_ram_bytes=1_000_000),
                      source(point_record_bytes=4000), source(file_bytes=20_000_000)):
            self.assertEqual(planner.plan(facts).strategy, ViewStrategy.BUILD_VIEW_CACHE)

    def test_profile_cannot_raise_limit(self):
        plan = PointCloudViewStrategyPlanner(direct_available=True).plan(
            source(point_count=5_000_000, performance_profile={"direct_point_ceiling": 9_000_000}))
        self.assertEqual(plan.strategy, ViewStrategy.BUILD_VIEW_CACHE)

    def test_only_fully_verified_cache_is_reused(self):
        planner = PointCloudViewStrategyPlanner()
        self.assertEqual(planner.plan(source(), cache_state=CacheState.VALID,
            cache_identity_matches=True, cache_file_verified=True).strategy,
            ViewStrategy.REUSE_VIEW_CACHE)
        for state in CacheState:
            plan = planner.plan(source(), cache_state=state, cache_identity_matches=True)
            self.assertEqual(plan.strategy, ViewStrategy.BUILD_VIEW_CACHE)

    def test_identity_changes_on_scientific_or_policy_input(self):
        original = cache_key(cache_identity(source(), "untwine-1.5"))
        for facts in (source(modified_ns=124), source(crs="unknown"),
                      source(dimensions=("X", "Y", "Z")), source(fingerprint="b" * 64)):
            self.assertNotEqual(original, cache_key(cache_identity(facts, "untwine-1.5")))
        self.assertNotEqual(original, cache_key(cache_identity(source(), "untwine-1.6")))

    def test_invalid_facts_rejected(self):
        for values in ({"point_count": -1}, {"file_bytes": True}, {"fingerprint": "../x"},
                       {"available_ram_bytes": -1}, {"bounds": (0, 0, 0, -1, 2, 3)}):
            with self.assertRaises(ValueError):
                source(**values)

    def test_session_hint_cannot_replace_source_or_trust_another_cloud(self):
        data = {"sha256": "a" * 64, "strategy": "BUILD_VIEW_CACHE",
                "cache_fingerprint": "b" * 64, "render_source": "not-authoritative.laz"}
        hint = session_cache_hint(data, "a" * 64)
        self.assertEqual(hint["source_sha256"], "a" * 64)
        self.assertNotIn("render_source", hint)
        self.assertEqual(session_cache_hint(data, "c" * 64), {})


class ViewCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = ViewCache(self.root / "viewer-cache")
        self.identity = cache_identity(source(), "untwine-test")

    def verify(self, path, identity):
        return path.read_bytes() == b"verified fixture" and identity == self.identity

    def publish(self):
        with self.cache.build(self.identity) as temp:
            staged = temp / "view.copc.laz"
            staged.write_bytes(b"verified fixture")
            return self.cache.publish(self.identity, staged, verify=self.verify)

    def test_success_reuses_only_verified_output(self):
        output = self.publish()
        self.assertEqual(self.cache.reusable(self.identity, self.verify), output)
        self.assertFalse((output.parent / "temp").exists())
        output.write_bytes(b"invalid fixture!")
        self.assertIsNone(self.cache.reusable(self.identity, self.verify))

    def test_failure_cleans_scratch_and_retry(self):
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            with self.cache.build(self.identity) as temp:
                (temp / "partial").write_bytes(b"partial")
                raise RuntimeError("cancelled")
        self.assertEqual(self.cache.read(self.identity)["state"], "FAILED")
        self.assertFalse((self.cache.entry(self.identity) / "temp").exists())
        self.assertTrue(self.publish().exists())

    def test_same_size_corruption_rejected_even_if_metadata_probe_passes(self):
        output = self.publish()
        output.write_bytes(b'corrupt! fixture')
        self.assertEqual(output.stat().st_size, len(b'verified fixture'))
        self.assertIsNone(self.cache.reusable(self.identity, lambda *args: True))
        self.assertEqual(self.cache.read(self.identity)['state'], 'STALE')

    def test_missing_cache_is_rebuildable(self):
        output = self.publish()
        output.unlink()
        self.assertIsNone(self.cache.reusable(self.identity, self.verify))
        self.assertTrue(self.publish().exists())

    def test_probe_exception_is_stale_not_uncaught_failure(self):
        self.publish()
        def broken(*args):
            raise RuntimeError('invalid COPC hierarchy')
        self.assertIsNone(self.cache.reusable(self.identity, broken))
        self.assertFalse((self.cache.entry(self.identity) / 'build.lock').exists())

    def test_reuse_verification_holds_cleanup_lock(self):
        output = self.publish()
        def verify(path, identity):
            self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0), [])
            return self.verify(path, identity)
        self.assertEqual(self.cache.reusable(self.identity, verify), output)

    def test_lock_not_stolen(self):
        with self.cache.build(self.identity):
            with self.assertRaises(FileExistsError):
                with self.cache.build(self.identity):
                    self.fail("Concurrent build acquired a lock")
        self.assertFalse((self.cache.entry(self.identity) / "build.lock").exists())

    def test_failed_verification_never_publishes(self):
        with self.assertRaises(ValueError):
            with self.cache.build(self.identity) as temp:
                staged = temp / "view.copc.laz"
                staged.write_bytes(b"bad")
                self.cache.publish(self.identity, staged, verify=self.verify)
        self.assertFalse((self.cache.entry(self.identity) / "view.copc.laz").exists())

    def test_cannot_publish_original(self):
        original = self.root / "source.laz"
        original.write_bytes(b"original")
        with self.assertRaises(ValueError):
            self.cache.publish(self.identity, original, verify=lambda *args: True)
        self.assertEqual(original.read_bytes(), b"original")

    def test_cleanup_never_removes_sessions_or_protected_cache(self):
        output = self.publish()
        session = self.cache.root / "session.json"
        session.write_text("journal", encoding="ascii")
        self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0,
                         protected_keys=(output.parent.name,)), [])
        self.assertTrue(output.exists())
        (output.parent / "journal.json").write_text("protected", encoding="ascii")
        self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0), [])
        self.assertTrue(session.exists())
        self.assertTrue(output.exists())

    def test_cleanup_old_unreferenced_cache(self):
        output = self.publish()
        self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0),
                         [output.parent.name])
        self.assertFalse(output.exists())

    def test_cleanup_leaves_active_build(self):
        with self.cache.build(self.identity) as temp:
            self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0), [])
            self.assertTrue(temp.exists())

    def test_read_lease_protects_cache(self):
        output = self.publish()
        with self.cache.lease(output.parent.name):
            self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0), [])
            self.assertTrue(output.exists())
        self.assertEqual(self.cache.cleanup(max_bytes=0, older_than_seconds=0), [output.parent.name])

    def test_only_confirmed_dead_builder_lock_is_recovered(self):
        output = self.publish()
        lock = output.parent / "build.lock"
        lock.write_text("12345", encoding="ascii")
        self.assertFalse(self.cache.recover_interrupted(self.identity, alive=lambda pid: True))
        self.assertTrue(lock.exists())
        self.assertTrue(self.cache.recover_interrupted(self.identity, alive=lambda pid: False))
        self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
