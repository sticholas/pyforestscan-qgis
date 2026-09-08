"""Transport security and bounded reads without QGIS/scientific dependencies."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pyforestscan_qgis.core.point_cloud.asset_server import (
    MAX_RANGE_BYTES, ViewerAssetServer, byte_range, source_file,
)


class AssetServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cloud = self.root / "tiny.copc.laz"
        self.cloud.write_bytes(bytes(range(256)) * 4)
        self.asset = self.root / "viewer.html"
        self.asset.write_text("<html>viewer</html>")
        self.before = hashlib.sha256(self.cloud.read_bytes()).hexdigest()
        self.server = ViewerAssetServer(assets={"viewer.html": self.asset}, source=self.cloud)
        self.addCleanup(self.server.close)

    def request(self, route, headers=None, method="GET"):
        return urlopen(Request(self.server.base_url + route, headers=headers or {}, method=method), timeout=2)

    def test_indexed_source_byte_ranges_and_source_immutable(self):
        with self.request("source/cloud.copc.laz", {"Range": "bytes=100-119"}) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), self.cloud.read_bytes()[100:120])
            self.assertEqual(response.headers["Content-Range"], "bytes 100-119/1024")
        self.assertEqual(hashlib.sha256(self.cloud.read_bytes()).hexdigest(), self.before)

    def test_head_and_explicit_asset_only(self):
        with self.request("viewer.html", method="HEAD") as response:
            self.assertEqual(response.read(), b"")
        for route in ("secret.txt", "../viewer.html", "%2e%2e/viewer.html", "source/../viewer.html"):
            with self.subTest(route=route), self.assertRaises(HTTPError):
                self.request(route)

    def test_reject_wrong_host_origin_and_token(self):
        for headers in ({"Host": "evil.example"}, {"Origin": "https://evil.example"}):
            with self.assertRaises(HTTPError) as error:
                self.request("viewer.html", headers)
            self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError):
            urlopen(self.server.base_url.replace(self.server.base_url.split("/")[-2], "wrong") + "viewer.html", timeout=2)

    def test_no_write_api(self):
        with self.assertRaises(HTTPError) as error:
            self.request("source/cloud.copc.laz", method="POST")
        self.assertEqual(error.exception.code, 501)

    def test_range_limits(self):
        for value in ("bytes=-10", "bytes=5-4", "bytes=0-1,4-8", f"bytes=0-{MAX_RANGE_BYTES}"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                byte_range(value, MAX_RANGE_BYTES * 2)
        self.assertEqual(byte_range("bytes=5-", 10), (5, 10))
        self.assertEqual(byte_range(None, 0), (0, 0))

    def test_large_source_requires_range_but_allows_head(self):
        with self.cloud.open("wb") as stream:
            stream.truncate(MAX_RANGE_BYTES + 1)
        with self.assertRaises(HTTPError):
            self.request("source/cloud.copc.laz")
        with self.request("source/cloud.copc.laz", method="HEAD") as response:
            self.assertEqual(int(response.headers["Content-Length"]), MAX_RANGE_BYTES + 1)
        with self.request("source/cloud.copc.laz", {"Range": "bytes=0-3"}) as response:
            self.assertEqual(len(response.read()), 4)
        self.assertEqual(self.server.stats()["source_requests"], 1)
        self.assertEqual(self.server.stats()["range_requests"], 1)

    def test_ept_node_allowlist(self):
        self.assertEqual(source_file(self.root, "ept-data/1-2-3-4.laz"), self.root / "ept-data/1-2-3-4.laz")
        for route in ("../outside", "ept-data/../private.txt", "ept-data/passwords.json", "ept-sources/1.json"):
            with self.assertRaises(ValueError):
                source_file(self.root, route)

    def test_unprepared_las_rejected(self):
        raw = self.root / "raw.las"
        raw.write_bytes(b"LAS")
        with self.assertRaises(ValueError):
            ViewerAssetServer(assets={}, source=raw)

    def test_close_is_idempotent(self):
        self.server.close()
        self.server.close()
        self.assertFalse(self.server._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
