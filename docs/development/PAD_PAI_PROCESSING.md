# PAD and PAI Processing Manual Testing

Phase 13A enables Plant Area Density (PAD) and Plant Area Index (PAI) as real
adapter-backed PyForestScan products for a single small lidar dataset. CHM and
Canopy Cover remain implemented. batch processing and folder cataloging remain out of scope.

## Exact PyForestScan API Used

The adapter owns every direct PyForestScan call:

```python
from pyforestscan import assign_voxels, calculate_pad, calculate_pai
from pyforestscan.handlers import read_lidar, create_geotiff
```

The PAD runtime sequence is:

1. `pyforestscan.handlers.read_lidar(input_file, crs, hag=True)` reads the active
   LAS, LAZ, COPC, or EPT dataset and requests `HeightAboveGround`.
2. `pyforestscan.assign_voxels(point_array, (grid_resolution, grid_resolution,
   voxel_height))` creates height-binned voxel return counts and the spatial
   extent.
3. `pyforestscan.calculate_pad(voxel_returns, voxel_height=voxel_height,
   beer_lambert_constant=1.0, drop_ground=True)` creates a 3D PAD array.
4. The plugin adapter writes that 3D array to a multi-band GeoTIFF using
   `rasterio`, with one raster band per vertical height bin.

The PAI runtime sequence is:

1. `pyforestscan.handlers.read_lidar(input_file, crs, hag=True)` reads the active
   dataset and requests `HeightAboveGround`.
2. `pyforestscan.assign_voxels(point_array, (grid_resolution, grid_resolution,
   voxel_height))` creates voxel return counts and extent.
3. `pyforestscan.calculate_pad(voxel_returns, voxel_height=voxel_height)` creates
   the internal 3D PAD prerequisite.
4. `pyforestscan.calculate_pai(pad, voxel_height, min_height=1.0,
   max_height=None)` collapses PAD into a 2D PAI array.
5. `pyforestscan.handlers.create_geotiff(pai, output_path, crs, extent)` writes
   the single-band PAI GeoTIFF.

No QGIS UI class or Processing algorithm calls PyForestScan directly.

## Output Representation

PAI is naturally a 2D raster, so Phase 13A writes it as a single-band GeoTIFF:

```text
<run_folder>/outputs/pai.tif
```

PAD is a height-binned 3D product, so Phase 13A does not flatten it into a false
2D summary. The chosen safe representation is a multi-band GeoTIFF:

```text
<run_folder>/outputs/pad.tif
```

Each band represents one vertical bin. The bin height comes from Product
Planner's `height_bin_size` parameter. Band 1 is the first vertical bin returned
by PyForestScan after ground handling. The adapter currently writes bands in the
same order returned by `calculate_pad`; it does not yet write per-band metadata
labels.

## Expected Run Folder Outputs

Mission Control writes PAD and PAI outputs inside the active run folder:

```text
<chosen_output_folder>/pyforestscan_runs/<YYYYMMDD_HHMMSS_datasetstem>/
  outputs/pad.tif
  outputs/pai.tif
  logs/job_summary.json
```

If the user changes either output filename in Planning, that filename is used
inside `outputs/`. `job_summary.json` records the selected grid resolution,
height bin size, output filenames, and result paths such as `pad_geotiff` and
`pai_geotiff`.

## Manual QGIS Test

1. Start QGIS with the verified OSGeo4W/QGIS Python environment.
2. Open PyForestScan Mission Control.
3. Run Environment and confirm the status is `READY`.
4. On Dataset, choose a small LAS/LAZ/COPC/EPT dataset with a known CRS and an
   output folder.
5. Run Dataset Explorer and confirm the Dataset Report link appears in Results.
6. On Planning, select `PAD` and/or `PAI`, choose a conservative grid resolution
   such as `1.0`, choose a height bin size such as `1.0` or `2.0`, and confirm
   PAD/PAI output filenames.
7. Build the plan.
8. On Processing, choose `Start Processing Job`.
9. Confirm the pipeline reaches `completed` and the requested GeoTIFFs exist in
   `outputs/`.
10. Confirm QGIS adds the PAD and PAI raster layers automatically when possible.
11. Open Results and verify Dataset Report, Product Plan, Job Summary, Output
    Folder, Products, PAD Output, and PAI Output links.
12. Open `logs/job_summary.json` and confirm:
    - `status` is `completed`
    - `processing_executed` is `true`
    - `scientific_outputs_created` is `true`
    - `parameters` records grid resolution, height bin size, and output filenames
    - `pad_geotiff` and/or `pai_geotiff` results point to GeoTIFF outputs

## Manual QA Checklist

- PAI opens as a single-band raster in QGIS.
- PAD opens as a multi-band raster in QGIS.
- CRS matches the input dataset CRS reported by Dataset Explorer.
- Extent aligns with the point cloud footprint.
- PAI values are non-negative and spatially plausible.
- PAD bands are non-negative and vary vertically where canopy structure exists.
- Changing height bin size changes PAD band count and PAI integration behavior.
- `job_summary.json` records selected parameters and output paths.
- Re-running with different output filenames produces distinct GeoTIFFs.

## Failure Checks

- Missing CRS should fail before PyForestScan is called.
- Missing `HeightAboveGround` in the returned point array should fail clearly.
- Invalid grid resolution, height bin size, or output filename should fail clearly.
- Missing PyForestScan, PDAL, rasterio, GDAL, or numpy should produce a
  plugin-owned processing error and failed job summary.
- If a GeoTIFF writer does not create a file, the job should fail instead of
  reporting partial success.

## Limitations

- Small datasets only; no tiling, chunking, or batch execution yet.
- PAD multi-band GeoTIFFs do not yet include per-band height labels.
- PAD is styled using band 1 only when automatically loaded into QGIS.
- PAI uses `min_height=1.0` and no maximum height by default.
- Beer-Lambert and extinction coefficient controls are not exposed in Mission
  Control yet.
- HAG is requested with `hag=True`; DTM-backed height-normalization controls are
  not wired.
