# Manual QA Script

This script validates the full plugin workflow for the internal release candidate. Use a small, known-good lidar dataset first.

## 1. Install And Open

1. Build `dist/pyforestscan_qgis.zip`.
2. Install it in QGIS with Plugin Manager > Install from ZIP.
3. Open PyForestScan Mission Control.
4. Confirm the window opens floating, large, and movable.
5. Confirm Home shows environment status, active dataset, batch status, and clear Start Single Dataset / Start Batch actions.

## 2. Environment

1. Open Environment.
2. Click Refresh Environment.
3. Confirm PyForestScan, PDAL, GDAL, rasterio, and numpy report PASS in the expected QGIS Python environment.
4. If not READY, confirm messages are clear and no traceback appears.

## 3. Single Dataset Workflow

1. Open Dataset.
2. Select a LAS/LAZ/COPC/EPT dataset and output folder.
3. Run Dataset Explorer.
4. Confirm Dataset Summary, Spatial Preview, bounds, CRS, and warnings are readable.
5. Add Footprint Layer and Zoom to Footprint.
6. Open Scientific Advisor and confirm executive summary, warnings, recommended products, parameters, and next steps appear.
7. Open Planning, select products, and Build Plan.
8. Open Processing and confirm selected products, output folder, and Processing Footprint appear without raw JSON paths in the primary view.
9. Run selected products.
10. Confirm Results lists friendly links before technical files.

## 4. Product Output QA

For each generated product, confirm output exists in the run folder and job summary records it.

- CHM: `outputs/chm.tif`, grayscale display, CRS/extent look correct.
- Canopy Cover: `outputs/canopy_cover.tif`, grayscale display, values look plausible.
- PAD: `outputs/pad.tif`, authoritative multiband height-bin GeoTIFF, default grayscale height-slice display, no crash if fewer bands.
- PAI: `outputs/pai.tif`, grayscale display.
- FHD: `outputs/fhd.tif`, grayscale display.
- Rumple: `outputs/rumple_summary.csv`, table/report link visible.

## 5. Batch Workflow

1. Open Batch.
2. Select an input folder and discover files.
3. Select a small set of files, output folder, products, and shared settings.
4. Confirm output loading into QGIS is off by default.
5. Run Preflight and resolve blockers.
6. Run Sequential batch.
7. Confirm manifest and batch summaries are written.
8. Retry failed files if any.
9. Run a small Parallel Safe batch with two workers after acknowledging warnings.
10. Confirm External Worker mode is not selectable.

## 6. Regression Checks

- No Python traceback appears in the QGIS Python console.
- Environment Check Processing algorithm still runs.
- Dataset Explorer Processing algorithm still writes JSON/CSV/HTML.
- Product Planner Processing algorithm still writes JSON/CSV/HTML.
- Placeholder toolbox entries remain harmless.
- Closing and reopening Mission Control preserves normal behavior.
