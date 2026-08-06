# EPT Repository Handling

Phase 27J corrects Polygon Area Processing so EPT datasets are treated as logical spatial sources rather than millions of internal node files.

## Selection Normalization

The plugin recognizes these selections as the same EPT dataset:

- `ept.json`
- a directory containing `ept.json`
- an `ept-data` directory whose parent contains `ept.json`
- paths inside an EPT hierarchy whose ancestor contains `ept.json`

All are normalized to the EPT root and logical source `ept.json`. If the user chooses `ept-data`, Mission Control reports that the EPT data folder was detected and the parent EPT dataset is being used.

## Catalog Pruning

Catalog traversal registers `ept.json` once and prunes:

- `ept-data`
- `ept-hierarchy`
- EPT node `.laz` files
- EPT support files that are not spatial sources

This pruning happens during traversal, before millions of internal files can be enumerated.

## Incorrect Catalog Repair

Older catalogs may contain internal EPT node records. The repair path detects node-dominated EPT catalogs, backs up the catalog, deletes internal EPT node records, registers one logical `ept.json` record, and rebuilds the RTree entries for that logical source. Repair does not traverse the EPT node tree.

## Execution

EPT Polygon Area Processing uses one logical source. The request carries automatic EPT bounds in PyForestScan format `([xmin, xmax], [ymin, ymax])` and retains the exact polygon WKT for clipping. PBM backend Python imports PyForestScan and reads the EPT; QGIS Python prepares the request and monitors results.

Local tiled LAS/LAZ processing still uses catalog query plus staged clipped files. COPC follows the logical source pattern when cataloged as a logical source.


## Phase 27K Polygon Transport

EPT polygon jobs now keep the EPT source as one logical  input and pass polygon-derived EPT bounds to the backend. Exact clipping geometry is serialized in the job spec and materialized inside the PBM job workspace as a vector file before PyForestScan is called. WKT is diagnostics content, not a polygon filename.

## Bounds contract and diagnostics

EPT repository processing must pass polygon-derived bounds to PyForestScan as list coordinate ranges. Derived PDAL expressions are recorded in diagnostics for troubleshooting, but manifests keep `ept_bounds` as a typed JSON object.

## Phase 27N Native EPT Selection

EPT repository identity is resolved before polygon preflight and no longer depends on polygon shape. Native EPT preflight selects one logical `ept.json` source by comparing a CRS-safe polygon envelope with the root EPT extent.

## Phase 27S CRS Repair

EPT CRS parsing now uses the shared resolver documented in [EPT CRS Resolution](EPT_CRS_RESOLUTION.md). `authority=EPSG` plus `horizontal=6635` resolves to `EPSG:6635`; bare authority strings such as `EPSG` are rejected and never serialized into comparison CRS, EPT bounds, or execution manifests.

Saved EPT state with incomplete CRS metadata is treated as stale. When `ept.json` contains a usable WKT, PROJJSON, or authority plus horizontal code, the next repository resolution recomputes the source CRS without a full EPT catalog rebuild.
## Bounded processing
EPT nodes are never Batch inputs. Large CHM requests issue aligned bounded reads against one logical `ept.json` and checkpoint core rasters.
