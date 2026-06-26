# CHM Processing Manual Testing

Phase 10B stabilizes the first production product path: Canopy Height Model
(CHM) generation for a single small lidar dataset. All other planned products
remain not implemented.

## Exact PyForestScan API Used

The adapter owns every direct PyForestScan call:

```python
from pyforestscan import calculate_chm
from pyforestscan.handlers import read_lidar, create_geotiff
```

The runtime call sequence is:

1. `pyforestscan.handlers.read_lidar(input_file, crs, hag=True)` reads the active
   LAS, LAZ, COPC, or EPT dataset and requests `HeightAboveGround` values through
   PyForestScan/PDAL.
2. `pyforestscan.calculate_chm(point_array, (grid_resolution, grid_resolution),
   interpolation=<selected method>, interp_valid_region=<selected boolean>, interp_clean_edges=<selected boolean>)`
   creates the CHM array and spatial extent.
3. `pyforestscan.handlers.create_geotiff(chm, output_path, crs, extent)` writes
   the single-band GeoTIFF.

No QGIS UI class or Processing algorithm calls PyForestScan directly.

## Expected Output Paths

Mission Control writes CHM outputs inside the active run folder:

```text
<chosen_output_folder>/pyforestscan_runs/<YYYYMMDD_HHMMSS_datasetstem>/
  outputs/<chosen_chm_filename>.tif
  logs/job_summary.json
```

`job_summary.json` records selected CHM parameters and the CHM GeoTIFF as a
`chm_geotiff` result when the job succeeds.

## Manual QGIS Test

1. Start QGIS with the verified OSGeo4W/QGIS Python environment.
2. Open PyForestScan Mission Control.
3. Run Environment and confirm the status is `READY`.
4. On Dataset, choose a small LAS/LAZ/COPC/EPT dataset with a known CRS and an
   output folder.
5. Run Dataset Explorer and confirm the Dataset Report link appears in Results.
6. On Planning, leave only `Canopy Height Model (CHM)` selected for the first
   test, choose a conservative grid resolution such as `1.0`, choose interpolation
   and cleanup options, confirm the output filename, and build the plan.
7. On Processing, choose `Start CHM Job`.
8. Confirm the pipeline reaches `completed` and the chosen CHM GeoTIFF exists in `outputs/`.
9. Confirm QGIS adds the CHM raster layer automatically when possible.
10. Open Results and verify Dataset Report, Product Plan, Job Summary, Output
    Folder, and Products links.
11. Open `logs/job_summary.json` and confirm:
    - `status` is `completed`
    - `processing_executed` is `true`
    - `scientific_outputs_created` is `true`
    - `parameters` records grid resolution, interpolation, valid-region interpolation, clean edges, and output filename
    - a `chm_geotiff` result points to the CHM GeoTIFF

## Failure Checks

- If CRS is missing from Dataset Explorer JSON, the CHM pipeline should fail
  clearly before calling PyForestScan.
- If PyForestScan, PDAL, rasterio, or GDAL is unavailable in QGIS Python, the
  adapter should raise a plugin-owned processing error and write a failed job
  summary.
- If the output folder is not writable or the output filename is invalid, the job
  should fail clearly and write a failed summary.
- If the GeoTIFF writer does not create a file, the job should fail instead of
  reporting partial success.
- If non-CHM products are selected, they remain skipped/not implemented and do
  not create rasters.

## Manual QA Checklist

- Output GeoTIFF opens in QGIS.
- CHM values look reasonable for the forest/site and contain no obvious all-zero
  or all-nodata result.
- CRS matches the input dataset CRS reported by Dataset Explorer.
- Extent aligns with the point cloud footprint.
- Edge artifacts are acceptable for the chosen interpolation and cleanup options.
- `job_summary.json` records the selected parameters and output path.
- Re-running with a different output filename produces a distinct GeoTIFF.

## Troubleshooting

- Missing CRS: rerun Dataset Explorer and confirm CRS metadata is present before
  processing.
- Height normalization warnings: review ground classification and CHM values;
  Phase 10B requests HAG through PyForestScan/PDAL but does not provide a DTM
  workflow.
- Large dataset warnings: use a smaller test dataset first because Phase 10B does
  not tile processing.
- Output missing: inspect `logs/job_summary.json`; the job should be `failed` if
  the GeoTIFF was not created.
- QGIS layer does not load: confirm the GeoTIFF exists, then add it manually from
  `outputs/`; automatic loading is best-effort.

## Limitations

- Small datasets only; no tiling or batch execution yet.
- HAG is requested with `hag=True`; DTM-backed height normalization is not wired.
- Interpolation controls are available, but no DTM-backed HAG configuration is exposed yet.
- Basic layer styling/statistics are best-effort; no publication symbology, pyramids, or layout is applied.
- PAI, PAD, FHD, canopy cover, and rumple remain unimplemented.
