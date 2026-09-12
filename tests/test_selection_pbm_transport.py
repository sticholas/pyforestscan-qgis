import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.backend_runner.job_spec import build_job_spec_from_request
from pyforestscan_qgis.backend_runner.run_processing_job import _request_from_spec
from pyforestscan_qgis.core.types import ChmRequest


class SelectionPbmTransportTests(unittest.TestCase):
    def test_vertical_selection_survives_pbm_job_spec_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = ChmRequest(
                input_path=root / "forest.laz", output_path=root / "chm.tif",
                grid_resolution=1.0, crs="EPSG:32604",
                bounds=((0.0, 0.0), (10.0, 8.0)),
                selection_vertical_axis="HeightAboveGround",
                selection_height_range=(2.0, 12.0),
            )
            spec = build_job_spec_from_request("chm", request, run_folder=root)
            restored = _request_from_spec(type(spec).from_dict(spec.to_dict()))
        self.assertEqual(restored.bounds, ((0.0, 0.0), (10.0, 8.0)))
        self.assertEqual(restored.selection_vertical_axis, "HeightAboveGround")
        self.assertEqual(restored.selection_height_range, (2.0, 12.0))
