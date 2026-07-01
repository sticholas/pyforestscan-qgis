# Output Products

PyForestScan QGIS produces scientific products, planning reports, batch summaries, and workspace records. This document defines the current output families and naming expectations for internal release.

## Scientific Raster Products

| Product | Default output | QGIS display | Notes |
| --- | --- | --- | --- |
| Canopy Height Model (CHM) | `outputs/chm.tif` | Grayscale | Height surface generated from LiDAR-derived canopy heights. |
| Canopy Cover | `outputs/canopy_cover.tif` | Grayscale | Fraction or proportion-style raster; default fallback display range is 0-1. |
| Plant Area Density (PAD) | `outputs/pad.tif` | RGB composite using bands 5/3/2 when available | Multi-band height-bin raster. Shorter stacks fall back safely. |
| Plant Area Index (PAI) | `outputs/pai.tif` | Grayscale | 2D integrated plant area metric. |
| Foliage Height Diversity (FHD) | `outputs/fhd.tif` | Grayscale | 2D diversity metric derived from vertical foliage distribution. |
| Point Density | User-selected GeoTIFF in Advanced Toolbox | Grayscale | Expert Processing Toolbox product. |
| Voxel Statistic | User-selected GeoTIFF in Advanced Toolbox | Grayscale | Expert Processing Toolbox product for selected dimension/statistic. |
| Digital Terrain Model (DTM) | User-selected GeoTIFF in Advanced Toolbox | Grayscale | Expert Processing Toolbox product. |

Raster products should record processing parameters and output paths in job summaries or Processing results. QGIS layer names should use concise product names and dataset/run context.

## Table and Summary Products

| Product | Default output | Notes |
| --- | --- | --- |
| Rumple | `outputs/rumple.csv` | Scalar/table summary for PyForestScan 0.4.x; not forced into a fake raster. |
| Batch summary | `batch_summary.json`, `batch_summary.csv`, `batch_summary.html` | Written in the batch folder and updated during long-running batches. |
| Final run summary | `reports/final_run_summary.html` where available | User-facing summary of generated products and warnings. |
| Dataset summary | `tables/dataset_summary.csv` | Dataset Explorer table output. |
| Product plan | `tables/product_plan.csv` | Product Planner table output. |

## Planning and Diagnostic Reports

Dataset Explorer writes:

- `reports/dataset_report.json`
- `reports/dataset_report.html`
- `tables/dataset_summary.csv`

Product Planner writes:

- `reports/product_plan.json`
- `reports/product_plan.html`
- `tables/product_plan.csv`

Job execution writes:

- `logs/job_summary.json`
- Product output files in `outputs/`
- Final user-facing run report when available

Internal JSON files are hidden from the default Mission Control workflow but remain available under technical details for reproducibility and support.

## Point Cloud Outputs

Advanced Toolbox workflows may write LAS/LAZ point-cloud outputs for preprocessing, cleaning, filtering, or Height Above Ground normalization. These outputs should preserve CRS metadata when available and should not be loaded into QGIS unless the user explicitly chooses an appropriate workflow.

## Workspace Outputs

Workspace persistence lives in `.pyforestscan/` under the selected output root. It stores session state, timeline events, recent workspaces, run history, and user notes. Workspace files are not scientific products; they make Mission Control resumable.

## Metadata Expectations

Every scientific output should preserve or record:

- Input source path or stable identifier.
- Coordinate reference system when known.
- Spatial resolution or voxel/bin size.
- Product-specific parameters.
- PyForestScan version when available.
- Plugin version.
- QGIS version when available.
- Processing timestamp.
- Output path and success/failure status.

## Styling Expectations

- CHM, Canopy Cover, PAI, FHD, Point Density, Voxel Statistic, and DTM load with grayscale styling by default.
- PAD loads as a multi-band RGB composite using red band 5, green band 3, and blue band 2 when at least five bands exist.
- Rumple is presented as a table/report link.
- Styling helps immediate inspection in QGIS and must not alter output values.
