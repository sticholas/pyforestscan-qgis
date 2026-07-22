"""Phase 27M exact raster masking tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.raster_mask import BackendRasterMaskService, QgisRasterMaskService, RasterMaskOptions


try:
    import numpy
    import rasterio
    from rasterio.transform import from_origin
except Exception:  # pragma: no cover - optional geospatial deps may be absent in minimal envs.
    numpy = None
    rasterio = None
    from_origin = None


@unittest.skipIf(rasterio is None, "rasterio is not available")
class Phase27MRasterMaskTests(unittest.TestCase):
    def _write_raster(self, path: Path, bands: int = 1) -> None:
        data = numpy.ones((bands, 10, 10), dtype="float32")
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=bands,
            dtype="float32",
            crs="EPSG:32610",
            transform=from_origin(0, 10, 1, 1),
            nodata=-9999.0,
        ) as dataset:
            dataset.write(data)
            dataset.update_tags(test_tag="kept")
            for index in range(1, bands + 1):
                dataset.set_band_description(index, f"Band {index}")

    def test_backend_mask_sets_outside_polygon_to_nodata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raster = Path(tmpdir) / "chm.tif"
            self._write_raster(raster)

            result = BackendRasterMaskService().mask(
                raster,
                "POLYGON ((2 2, 8 2, 8 8, 2 8, 2 2))",
                polygon_crs="EPSG:32610",
                processing_crs="EPSG:32610",
                options=RasterMaskOptions(all_touched=False),
            )

            self.assertEqual(result.status, "masked")
            with rasterio.open(raster) as dataset:
                data = dataset.read(1)
                self.assertEqual(data[0, 0], -9999.0)
                self.assertEqual(data[5, 5], 1.0)
                self.assertEqual(dataset.tags()["pyforestscan_mask_engine"], "backend_rasterio_mask")

    def test_backend_mask_preserves_multiband_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raster = Path(tmpdir) / "pad.tif"
            self._write_raster(raster, bands=3)

            result = BackendRasterMaskService().mask(
                raster,
                "POLYGON ((2 2, 8 2, 8 8, 2 8, 2 2))",
                polygon_crs="EPSG:32610",
                processing_crs="EPSG:32610",
                options=RasterMaskOptions(crop_to_polygon_extent=True, retain_unmasked_intermediate=True),
            )

            self.assertEqual(result.status, "masked")
            self.assertTrue(result.intermediate_path and result.intermediate_path.exists())
            with rasterio.open(raster) as dataset:
                self.assertEqual(dataset.count, 3)
                self.assertEqual(dataset.descriptions[0], "Band 1")
                self.assertLess(dataset.width, 10)

    def test_polygon_hole_remains_nodata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raster = Path(tmpdir) / "hole.tif"
            self._write_raster(raster)
            polygon = "POLYGON ((1 1, 9 1, 9 9, 1 9, 1 1), (4 4, 6 4, 6 6, 4 6, 4 4))"

            result = BackendRasterMaskService().mask(raster, polygon, polygon_crs="EPSG:32610", processing_crs="EPSG:32610")

            self.assertEqual(result.status, "masked")
            with rasterio.open(raster) as dataset:
                data = dataset.read(1)
                self.assertEqual(data[5, 5], -9999.0)
                self.assertEqual(data[2, 2], 1.0)


class Phase27MQgisMaskServiceTests(unittest.TestCase):
    def test_qgis_parameter_mapping(self) -> None:
        params = QgisRasterMaskService().build_parameters(
            input_path=Path("in.tif"),
            mask_path=Path("mask.gpkg"),
            output_path=Path("out.tif"),
            nodata=-9999.0,
            all_touched=True,
            crop_to_polygon_extent=True,
        )

        self.assertEqual(params["INPUT"], "in.tif")
        self.assertEqual(params["MASK"], "mask.gpkg")
        self.assertTrue(params["CROP_TO_CUTLINE"])
        self.assertTrue(params["KEEP_RESOLUTION"])
        self.assertIn("CUTLINE_ALL_TOUCHED", params["EXTRA"])


if __name__ == "__main__":
    unittest.main()
