"""The direct adapter must remain bounded and capability-scoped."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError

from pyforestscan_qgis.core.point_cloud.asset_server import ViewerAssetServer
from pyforestscan_qgis.core.point_cloud.direct_source import direct_metadata


def fixture(path, *, count=20_000, point_format=7, minor=4):
    data = bytearray(1024)
    data[:4] = b"LASF"
    data[24:26] = bytes((1, minor))
    data[104] = point_format
    struct.pack_into("<H", data, 105, 36)
    struct.pack_into("<I", data, 107, count)
    struct.pack_into("<Q", data, 247, count)
    struct.pack_into("<6d", data, 179, 10, 0, 20, 0, 5, -1)
    path.write_bytes(data)


class DirectSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "tiny.laz"
        fixture(self.path)

    def test_virtual_metadata_preserves_count_and_real_extent(self):
        result = direct_metadata(self.path)
        self.assertEqual(result["points"], 20_000)
        self.assertEqual(result["boundsConforming"], [0, 0, -1, 10, 20, 5])
        self.assertEqual(result["sourceStrategy"], "DIRECT")

    def test_large_or_unsupported_input_not_admitted_directly(self):
        for args in ({"count": 2_287_408}, {"point_format": 10}, {"minor": 3}):
            fixture(self.path, **args)
            with self.assertRaises(ValueError):
                direct_metadata(self.path)

    def test_transport_virtual_hierarchy_and_original_binary(self):
        original = self.path.read_bytes()
        sibling = self.path.with_name("secret.laz")
        sibling.write_bytes(b"not authorized")
        with ViewerAssetServer(assets={}, source=self.path) as server:
            with urlopen(server.base_url + "source/ept.json") as response:
                self.assertEqual(json.load(response)["points"], 20_000)
            with urlopen(server.base_url + "source/ept-hierarchy/0-0-0-0.json") as response:
                self.assertEqual(json.load(response), {"0-0-0-0": 20_000})
            with urlopen(server.base_url + "source/ept-data/0-0-0-0.laz") as response:
                self.assertEqual(response.read(), original)
            for route in ("source/ept-data/1-0-0-0.laz", "source/secret.laz",
                          "source/../secret.laz"):
                with self.assertRaises(HTTPError):
                    urlopen(server.base_url + route)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ["secret.laz", "tiny.laz"])


if __name__ == "__main__":
    unittest.main()
