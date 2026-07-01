# FHD and Rumple Processing Manual Testing

Phase 14A enables the remaining major PyForestScan products for a single small
lidar dataset: Foliage Height Diversity (FHD) and Rumple Index. CHM, Canopy
Cover, PAD, and PAI remain implemented. Batch processing, folder cataloging,
project files, embedded mini maps, and async worker changes remain out of scope.

## Exact PyForestScan API Used

The adapter owns every direct PyForestScan call:

```python
from pyforestscan import assign_voxels, calculate_fhd, calculate_chm, calculate_rumple
from pyforestscan.handlers import read_lidar, create_geotiff
```

The FHD runtime sequence is:

1. `pyforestscan.handlers.read_lidar(input_file, crs, hag=True)` reads the active
   LAS, LAZ, COPC, or EPT dataset and requests `HeightAboveGround`.
2. `pyforestscan.assign_voxels(point_array, (grid_resolution, grid_resolution,
   voxel_height))` creates voxel return counts and the spatial extent.
3. `pyforestscan.calculate_fhd(voxel_returns, voxel_height=voxel_height,
   min_height=0.0, max_height=None)` creates a 2D entropy raster.
4. `pyforestscan.handlers.create_geotiff(fhd, output_path, crs, extent)` writes
   the single-band FHD GeoTIFF.

The Rumple runtime sequence is:

1. `pyforestscan.handlers.read_lidar(input_file, crs, hag=True)` reads the active
   dataset and requests `HeightAboveGround`.
2. `pyforestscan.calculate_chm(point_array, (grid_resolution, grid_resolution),
   interpolation=<selected CHM interpolation>, ...)` creates an internal CHM
   prerequisite.
3. `pyforestscan.calculate_rumple(chm, (grid_resolution, grid_resolution),
   min_height=None)` computes one scalar rumple index.
4. The plugin adapter writes the scalar value and provenance fields to CSV.

No QGIS UI class or Processing algorithm calls PyForestScan directly.

## Output Representation

FHD is naturally a 2D raster, so Phase 14A writes it as a single-band GeoTIFF:

```text
<run_folder>/outputs/fhd.tif
```

Rumple is not naturally a raster in PyForestScan 0.4.0. The public API returns a
single `float` representing canopy surface area divided by planar area. Phase
14A therefore writes an honest scalar CSV table instead of fabricating a
`rumple.tif` raster:

```text
<run_folder>/outputs/rumple_summary.csv
```

The CSV contains `rumple_index`, grid resolution, optional minimum height, CRS,
and source extent fields.

## Manual QGIS Test

1. Start QGIS with the verified OSGeo4W/QGIS Python environment.
2. Open PyForestScan Mission Control.
3. Run Environment and confirm the status is `READY`.
4. On Dataset, choose a small LAS/LAZ/COPC/EPT dataset with a known CRS and an
   output folder.
5. Run Dataset Explorer and confirm the Dataset Report link appears in Results.
6. On Planning, select `FHD` and/or `Rumple`, choose a conservative grid
   resolution such as `1.0`, choose a height bin size for FHD, and confirm output
   filenames.
7. Build the plan.
8. On Processing, choose `Start Processing Job`.
9. Confirm the pipeline reaches `completed` and requested outputs exist in
   `outputs/`.
10. Confirm QGIS adds the FHD raster layer automatically when possible.
11. Confirm Rumple appears as a friendly CSV result link, not a raster layer.
12. Open `logs/job_summary.json` and confirm:
    - `status` is `completed`
    - `processing_executed` is `true`
    - `scientific_outputs_created` is `true`
    - `parameters` records grid resolution, height bin size, and output filenames
    - `fhd_geotiff` and/or `rumple_csv` results point to outputs

## Manual QA Checklist

- FHD opens as a single-band raster in QGIS.
- FHD CRS and extent align with the source dataset.
- FHD values are non-negative where canopy returns exist, with nodata where no
  height-bin returns are available.
- Rumple CSV opens in a text editor or spreadsheet and contains one
  `rumple_index` value.
- Rumple value is finite for datasets with valid CHM patches; `nan` may indicate
  no valid 2x2 CHM patches after masking.
- `job_summary.json` records selected parameters and output paths.

## Limitations

- Small datasets only; no tiling, chunking, or batch execution yet.
- FHD requires a height bin size because it is voxel based.
- Rumple is a scalar CSV output in PyForestScan 0.4.0, not a GeoTIFF.
- Rumple uses an internal CHM prerequisite; the CHM is not exported unless CHM is
  selected as a product.
- HAG is requested with `hag=True`; DTM-backed height-normalization controls are
  not wired.
