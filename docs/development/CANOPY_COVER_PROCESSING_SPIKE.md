# Canopy Cover Processing Manual Testing

Phase 11A enables the second real scientific product path: Canopy Cover
GeoTIFF generation for a single small lidar dataset. CHM remains implemented.
PAI, PAD, FHD, and rumple are implemented in later phases and should remain compatible with canopy cover.

## Exact PyForestScan API Used

The adapter owns every direct PyForestScan call:

```python
from pyforestscan import assign_voxels, calculate_pad, calculate_canopy_cover
from pyforestscan.handlers import read_lidar, create_geotiff
```

The runtime call sequence is:

1. `pyforestscan.handlers.read_lidar(input_file, crs, hag=True)` reads the active
   LAS, LAZ, COPC, or EPT dataset and requests `HeightAboveGround` through
   PyForestScan/PDAL.
2. `pyforestscan.assign_voxels(point_array, (grid_resolution, grid_resolution,
   1.0))` creates voxel return counts and the raster extent.
3. `pyforestscan.calculate_pad(voxel_returns, voxel_height=1.0)` creates an
   internal PAD prerequisite. PAD is not exposed as a product in Phase 11A.
4. `pyforestscan.calculate_canopy_cover(pad, 1.0,
   min_height=<selected canopy height threshold>, k=0.5)` creates a 2D canopy
   cover array with values expected in the range `[0, 1]`.
5. `pyforestscan.handlers.create_geotiff(canopy_cover, output_path, crs, extent)`
   writes the single-band GeoTIFF.

No QGIS UI class or Processing algorithm calls PyForestScan directly.

## Expected Output Paths

Mission Control writes canopy cover outputs inside the active run folder:

```text
<chosen_output_folder>/pyforestscan_runs/<YYYYMMDD_HHMMSS_datasetstem>/
  outputs/canopy_cover.tif
  logs/job_summary.json
```

If the user changes the output filename in Planning, that filename is used
inside `outputs/`. `job_summary.json` records selected canopy cover parameters
and the GeoTIFF as a `canopy_cover_geotiff` result when the job succeeds.

## Manual QGIS Test

1. Start QGIS with the verified OSGeo4W/QGIS Python environment.
2. Open PyForestScan Mission Control.
3. Run Environment and confirm the status is `READY`.
4. On Dataset, choose a small LAS/LAZ/COPC/EPT dataset with a known CRS and an
   output folder.
5. Run Dataset Explorer and confirm the Dataset Report link appears in Results.
6. On Planning, select `Canopy Cover`, choose a conservative grid resolution such
   as `1.0`, choose a canopy height threshold such as `2.0`, confirm the output
   filename, and build the plan.
7. On Processing, choose `Start Processing Job`. The selected products in the
   plan determine whether CHM, canopy cover, or both run.
8. Confirm the pipeline reaches `completed` and the canopy cover GeoTIFF exists
   in `outputs/`.
9. Confirm QGIS adds the canopy cover raster layer automatically when possible.
10. Open Results and verify Dataset Report, Product Plan, Job Summary, Output
    Folder, Products, and Canopy Cover Output links.
11. Open `logs/job_summary.json` and confirm:
    - `status` is `completed`
    - `processing_executed` is `true`
    - `scientific_outputs_created` is `true`
    - `parameters` records grid resolution, canopy cover height threshold, and
      output filename
    - a `canopy_cover_geotiff` result points to the canopy cover GeoTIFF

## Manual QA Checklist

- Output GeoTIFF opens in QGIS.
- Auto-loaded canopy cover uses grayscale styling and should not appear blank from a stale `0` to `0` display range.
- Values are in the expected canopy cover range, normally `0` to `1`, with nodata
  where source data are insufficient.
- CRS matches the input dataset CRS reported by Dataset Explorer.
- Extent aligns with the point cloud footprint.
- Increasing the canopy height threshold reduces or preserves cover; it should
  not increase cover in ordinary cases.
- `job_summary.json` records the selected parameters and output path.
- Re-running with a different output filename produces a distinct GeoTIFF.

## Failure Checks

- If CRS is missing from Dataset Explorer JSON, the canopy cover pipeline should
  fail clearly before calling PyForestScan.
- If PyForestScan, PDAL, rasterio, or GDAL is unavailable in QGIS Python, the
  adapter should raise a plugin-owned processing error and write a failed job
  summary.
- If the output folder is not writable or the output filename is invalid, the job
  should fail clearly and write a failed summary.
- If the GeoTIFF writer does not create a file, the job should fail instead of
  reporting partial success.
- PAI, PAD, FHD, and rumple should continue to run through their own pipelines
  when selected in later-phase workflows.

## Limitations

- Small datasets only; no tiling or batch execution yet.
- Vertical voxel height is fixed at `1.0` meter in Phase 11A.
- Internal PAD is calculated only as a prerequisite for canopy cover and is not
  exported.
- HAG is requested with `hag=True`; DTM-backed height normalization is not wired.
- Auto-loaded canopy cover uses grayscale styling with refreshed display statistics; no publication symbology, pyramids, or layout is applied.
