# Full Product Workflow Manual QA

Phase 15A stabilizes the complete single-dataset product workflow and polishes
Mission Control defaults.

## Expected Workflow

1. Open QGIS with the verified QGIS/OSGeo4W Python environment.
2. Start or reload the PyForestScan plugin.
3. Confirm Mission Control opens as a floating movable window.
4. Run Environment and confirm the status is `READY`.
5. On Dataset, select one LAS, LAZ, COPC, or EPT dataset and one output folder.
6. Run Dataset Explorer and confirm the run folder is created.
7. On Planning, select one or more products. Use `Select All Products` for the
   complete workflow.
8. Confirm product settings are visible:
   - grid resolution
   - height bin size for PAD, PAI, and FHD
   - CHM interpolation, valid region, and edge cleanup
   - canopy cover threshold
   - output filenames for CHM, Canopy Cover, PAD, PAI, FHD, and Rumple
9. Build the Product Plan.
10. On Processing, start the product job.
11. Confirm all selected product pipelines appear and the job reaches a final
    status.
12. Open Results and confirm friendly links for generated outputs.

## Expected Outputs

All outputs are written inside the active run folder:

```text
<chosen_output_folder>/pyforestscan_runs/<timestamp_dataset>/
  reports/dataset_report.html
  reports/product_plan.html
  logs/job_summary.json
  logs/job_summary.html
  outputs/chm.tif
  outputs/canopy_cover.tif
  outputs/pad.tif
  outputs/pai.tif
  outputs/fhd.tif
  outputs/rumple_summary.csv
```

Only selected products are generated. Rumple is a scalar CSV summary, not a
raster.

## QGIS Layer QA

- CHM, Canopy Cover, PAD, PAI, and FHD rasters load into QGIS when possible.
- Loaded raster layer names use the pattern `PyForestScan <Product> - <dataset>`.
- All loaded rasters use grayscale styling by default.
- No colorful ramps are applied automatically.
- PAD may load band 1 by default; users can manually inspect other bands in QGIS.
- Rumple appears as a CSV/report link and is not loaded as a raster layer.

## Summary QA

Open `logs/job_summary.html` and `logs/job_summary.json` and confirm:

- job status is recorded
- requested products are listed
- selected parameters are recorded
- all generated product paths are listed
- failed products, if any, are visible through pipeline status and error message

## Partial Failure Behavior

If one selected product fails, the job status is `failed` and the summary files
are still written. Outputs already produced by successful product pipelines remain
recorded. This is intentional: partial files are not hidden, but the overall job
must not report full success when any selected product failed.

## Large Dataset Warning QA

Use or mock a Dataset Explorer report with more than 5 million points. Product
Planner should show a `LARGE_POINT_COUNT` warning explaining that current
processing is single-file and may be slow or memory intensive.

## Current Limitations

- Single-dataset workflow only.
- No batch processing or folder cataloging.
- No project file workflow.
- No embedded mini map.
- Processing is synchronous; async worker overhaul is future work.
