"""Independent linked-selection and original-range index regression checks."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import unittest

from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, selection_mask
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
from pyforestscan_qgis.core.point_cloud.source_index import RawSpatialIndex


def definition(**values):
    return SelectionDefinition("selection", "session", "a"*64, "LAS",
        ((-1,-2),(11,-2),(11,2),(-1,2),(-1,-2)), "SOURCE_LOCAL:"+"a"*64,
        **values)


class LinkedSelectionContractTests(unittest.TestCase):
    def test_explicit_depth_and_immutable_profile(self):
        for values in ({"depth_mode":"VISIBLE_DEPTH"}, {"depth_mode":"CUSTOM_DEPTH_RANGE"},
                       {"depth_mode":"SLICE_CORRIDOR"},
                       {"profile_a":(0,0), "profile_b":(0,0), "profile_thickness":2}):
            with self.assertRaises(ValueError):
                definition(**values)
        ring = [[2,2],[8,2],[8,8],[2,8],[2,2]]
        item = definition(profile_a=[0,0], profile_b=[10,0], profile_thickness=2,
                          profile_geometry=ring, depth_mode="SLICE_CORRIDOR")
        ring[0][0] = 999
        self.assertEqual(item.profile_geometry[0], (2,2))

    @unittest.skipUnless(importlib.util.find_spec("shapely"), "Managed Shapely required")
    def test_top_side_depth_height_and_classes_intersect(self):
        import numpy as np
        # Coincident records must both survive; displayed LOD does not define membership.
        points = np.array([(5,0,5,3,5), (5,0,5,3,5), (5,1,5,3,5),
                           (5,1.01,5,3,5), (9,0,5,3,5), (5,0,9,3,5),
                           (5,0,5,9,5), (5,0,5,3,2), (1,0,5,3,5)],
                          dtype=[("X","f8"),("Y","f8"),("Z","f8"),
                                 ("HeightAboveGround","f8"),("Classification","u1")])
        item = definition(profile_a=(0,0), profile_b=(10,0), profile_thickness=2,
            profile_geometry=((2,2),(8,2),(8,8),(2,8),(2,2)),
            hag_filter=(2,4), classification_filter=(5,), depth_mode="SLICE_CORRIDOR")
        self.assertEqual(selection_mask(points, [item]).tolist(),
                         [True,True,True,False,False,False,False,False,False])
        clipped = replace(item, clip_geometry=((4,-.5),(6,-.5),(6,.5),(4,.5),(4,-.5)))
        self.assertEqual(int(selection_mask(points, [clipped]).sum()), 2)
        hag = replace(item, profile_axis="HeightAboveGround", hag_filter=None)
        self.assertTrue(selection_mask(points, [hag])[5])
        self.assertFalse(selection_mask(points, [hag])[6])
        subtract = replace(item, selection_id="subtract", selection_mode="SUBTRACT")
        self.assertFalse(selection_mask(points, [item, subtract]).any())

    @unittest.skipUnless(importlib.util.find_spec("pdal"), "Managed PDAL required")
    def test_raw_index_matches_original_records_and_rejects_stale_source(self):
        import json
        import numpy as np
        import pdal
        points = np.zeros(10000, dtype=[("X","f8"),("Y","f8"),("Z","f8"),("Classification","u1")])
        points["X"] = np.arange(len(points)) // 100
        points["Y"] = np.arange(len(points)) % 100
        points["Classification"] = 5
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for extension in ("las", "laz"):
                path = root / ("source."+extension)
                pdal.Pipeline(json.dumps([{"type":"writers.las", "filename":str(path),
                    "minor_version":4, "dataformat_id":6}]), arrays=[points]).execute()
                source = SourceIdentity.capture(path)
                index = RawSpatialIndex(source, root/"index")
                index.ensure()
                self.assertTrue(index.valid())
                envelopes = [(40,20,45,30), (42,22,44,28)]
                chunks = list(index.chunks(envelopes))
                candidate = np.concatenate(chunks)
                expected = points[(points["X"]>=40)&(points["X"]<=45)&(points["Y"]>=20)&(points["Y"]<=30)]
                actual = candidate[(candidate["X"]>=40)&(candidate["X"]<=45)&(candidate["Y"]>=20)&(candidate["Y"]<=30)]
                np.testing.assert_array_equal(actual["X"], expected["X"])
                np.testing.assert_array_equal(actual["Y"], expected["Y"])
                self.assertLess(len(candidate), len(points))
                with self.assertRaises(InterruptedError):
                    list(index.chunks(envelopes, cancelled=lambda: True))
                # A failed first build must not leave a usable/partial index.
                failed = RawSpatialIndex(source, root/("cancel-"+extension))
                with self.assertRaises(InterruptedError):
                    failed.ensure(cancelled=lambda: True)
                self.assertFalse(failed.path.exists())
                self.assertFalse(list(failed.root.glob("*.partial.sqlite")))
                with path.open("ab") as stream:
                    stream.write(b"changed")
                self.assertFalse(index.valid())
                with self.assertRaises(ValueError):
                    list(index.chunks(envelopes))


if __name__ == "__main__":
    unittest.main()
