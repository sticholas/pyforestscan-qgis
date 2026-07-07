"""QGIS-free tests for Mission Control Results output loading helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.dataset_report import build_dataset_explorer_report
from pyforestscan_qgis.ui.output_loading import (
    collect_loadable_outputs,
    compact_dataset_summary_lines,
    infer_output_result_type,
    output_loading_summary,
)

from tests.test_dataset_report import make_inspection


class ResultsOutputLoadingTests(unittest.TestCase):
    """Verify loadable output selection without importing QGIS."""

    def test_load_outputs_identifies_rasters_and_csv_tables(self) -> None:
        paths = (Path("chm.tif"), Path("pad.tiff"), Path("rumple_summary.csv"), Path("job_summary.html"))
        outputs = collect_loadable_outputs(paths)

        self.assertEqual([item.path.name for item in outputs], ["chm.tif", "pad.tiff", "rumple_summary.csv"])
        self.assertEqual([item.layer_kind for item in outputs], ["raster", "raster", "table"])

    def test_duplicate_output_paths_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chm = root / "chm.tif"
            chm.touch()
            outputs = collect_loadable_outputs((chm, chm, root / "other.tif"), existing_sources=(str(chm),))

        self.assertEqual([item.path.name for item in outputs], ["other.tif"])

    def test_loading_summary_text_is_concise(self) -> None:
        self.assertEqual(output_loading_summary(5, 5), "Loaded 5 outputs into QGIS.")
        self.assertEqual(output_loading_summary(1, 1), "Loaded 1 output into QGIS.")
        self.assertEqual(output_loading_summary(0, 0), "No loadable outputs found.")
        self.assertEqual(output_loading_summary(0, 3), "No new loadable outputs found.")

    def test_pad_styling_result_type_is_preserved(self) -> None:
        pad = Path("plot_pad.tif")
        outputs = collect_loadable_outputs((pad,), {pad: "pad_geotiff"})

        self.assertEqual(outputs[0].result_type, "pad_geotiff")
        self.assertEqual(infer_output_result_type(Path("pad.tif")), "pad_geotiff")

    def test_compact_dataset_summary_has_key_facts_only(self) -> None:
        report = build_dataset_explorer_report(make_inspection())
        lines = compact_dataset_summary_lines(report)

        self.assertEqual(len(lines), 6)
        self.assertTrue(lines[0].startswith("File: plot.las"))
        self.assertIn("Format: LAS", lines)
        self.assertTrue(any(line.startswith("CRS:") for line in lines))
        self.assertTrue(any(line.startswith("Readiness:") for line in lines))

    def test_dataset_summary_uses_content_sized_labels(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "pyforestscan_qgis/ui/pages.py").read_text(encoding="utf-8")

        self.assertIn('self.summary_text = _body_label(empty_state_message("dataset"))', source)
        self.assertIn('self.dataset_technical_text = _details_label("Dataset technical metadata appears after analysis.")', source)
        self.assertNotIn("self.summary_text.setMinimumHeight(COMPACT_LIST_HEIGHT)", source)
        self.assertNotIn("self.dataset_technical_text.setMinimumHeight(TECHNICAL_DETAIL_HEIGHT)", source)


if __name__ == "__main__":
    unittest.main()
