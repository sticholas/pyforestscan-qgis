# EPT Subset Extraction

Phase 27C adds a controlled workflow for extracting a smaller LAS/LAZ dataset from an Entwine Point Tile `ept.json` source. The workflow is intended for users who need to turn a bounded EPT area into a local point-cloud file before using the normal Dataset Explorer, Planning, Processing, and Results flow.

## Where It Appears

- Mission Control > Dataset > EPT Subset, collapsed by default.
- Processing Toolbox > PyForestScan > Input / I/O > Extract EPT Subset.

The Mission Control action is compact and dataset-focused. The Advanced Toolbox tool exposes the same `read_lidar` parameters for expert users.

## Parameters

The extraction maps to:

`pyforestscan.handlers.read_lidar(input_file, srs, bounds=None, thin_radius=None, hag=False, hag_dtm=False, dtm=None, crop_poly=False, poly=None, reproject=False)`

Then the result is written with `pyforestscan.handlers.write_las`.

Required inputs:

- `input_file`: an EPT `ept.json` source.
- `srs`: CRS/SRS text such as `EPSG:32610`.
- `output_las_laz`: a `.las` or `.laz` output path.

Optional inputs:

- `bounds`: `xmin,xmax,ymin,ymax` or `xmin,xmax,ymin,ymax,zmin,zmax`.
- `thin_radius`: positive thinning radius.
- `crop_poly` and `poly`: polygon WKT or polygon file path.
- `hag`: Delaunay Height Above Ground.
- `hag_dtm` and `dtm`: DTM-backed Height Above Ground.
- `reproject`: request reprojection while reading.

## Safety Rules

- Bounds extraction is limited to `ept.json` sources.
- `hag` and `hag_dtm` are mutually exclusive.
- `hag_dtm` requires a DTM path.
- `crop_poly` requires polygon WKT or a polygon file path.
- `thin_radius` must be greater than zero when provided.
- Output must end in `.las` or `.laz`.

## Mission Control Flow

1. Select an EPT `ept.json` source on the Dataset page.
2. Expand EPT Subset.
3. Enter CRS/SRS and any bounds, polygon, thinning, reprojection, or HAG options.
4. Choose or accept the default `outputs/ept_subset.laz` output.
5. Click Extract Subset.
6. After success, click Use Extracted Subset as Dataset to continue with the normal single-dataset workflow.

The subset extraction does not delete the original EPT source, PBM backend, existing outputs, or workspace state.
