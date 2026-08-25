"""Release-readiness regression checks."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pyforestscan_qgis.core.batch import BatchProductSettings, BatchRequest
from pyforestscan_qgis.core.batch_executor import BatchExecutor
from pyforestscan_qgis.core.batch_runner import BatchExecutionError
from pyforestscan_qgis.core.external_worker import EXTERNAL_WORKER_ENABLE_ENV, EXTERNAL_WORKER_MODE
from pyforestscan_qgis.core.product_plan import PRODUCT_LABELS, PRODUCT_OUTPUTS, ProductPlannerRequest
from pyforestscan_qgis.core.types import ProductType


class ReleaseReadinessTests(unittest.TestCase):
    """Protect product-facing names and disabled unsafe execution paths."""

    def test_product_names_are_standardized_for_release(self) -> None:
        self.assertEqual("Canopy Height Model (CHM)", PRODUCT_LABELS[ProductType.CHM])
        self.assertEqual("Canopy Cover", PRODUCT_LABELS[ProductType.CANOPY_COVER])
        self.assertEqual("Plant Area Density (PAD)", PRODUCT_LABELS[ProductType.PAD])
        self.assertEqual("Plant Area Index (PAI)", PRODUCT_LABELS[ProductType.PAI])
        self.assertEqual("Foliage Height Diversity (FHD)", PRODUCT_LABELS[ProductType.FHD])
        self.assertEqual("Rumple Index", PRODUCT_LABELS[ProductType.RUMPLE])

    def test_default_output_names_are_stable(self) -> None:
        request = ProductPlannerRequest(
            explorer_report_path=Path("dataset_report.json"),
            requested_products=(ProductType.CHM,),
            output_folder=Path("outputs"),
            grid_resolution=1.0,
        )

        self.assertEqual("chm.tif", request.chm_output_filename)
        self.assertEqual("canopy_cover.tif", request.canopy_cover_output_filename)
        self.assertEqual("pad.tif", request.pad_output_filename)
        self.assertEqual("pai.tif", request.pai_output_filename)
        self.assertEqual("fhd.tif", request.fhd_output_filename)
        self.assertEqual("rumple.tif", request.rumple_output_filename)
        self.assertEqual("chm.tif", PRODUCT_OUTPUTS[ProductType.CHM][0])
        self.assertEqual("canopy_cover.tif", PRODUCT_OUTPUTS[ProductType.CANOPY_COVER][0])
        self.assertEqual("pad.tif", PRODUCT_OUTPUTS[ProductType.PAD][0])
        self.assertEqual("pai.tif", PRODUCT_OUTPUTS[ProductType.PAI][0])
        self.assertEqual("fhd.tif", PRODUCT_OUTPUTS[ProductType.FHD][0])
        self.assertEqual("rumple.tif", PRODUCT_OUTPUTS[ProductType.RUMPLE][0])

    def test_external_worker_mode_remains_blocked_for_release(self) -> None:
        request = BatchRequest(
            input_folder=Path("input"),
            output_folder=Path("output"),
            recursive=False,
            datasets=(Path("input/sample.las"),),
            settings=BatchProductSettings(
                products=(ProductType.CHM,),
                grid_resolution=1.0,
                execution_mode=EXTERNAL_WORKER_MODE,
                max_workers=2,
                confirm_large_parallel=True,
            ),
        )

        with patch.dict("os.environ", {EXTERNAL_WORKER_ENABLE_ENV: ""}, clear=False):
            with self.assertRaises(BatchExecutionError):
                BatchExecutor().run(request)


if __name__ == "__main__":
    unittest.main()
