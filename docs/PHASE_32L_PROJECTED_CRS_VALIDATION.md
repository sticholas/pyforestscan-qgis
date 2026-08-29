# Phase 32L Projected CRS Validation

## Root cause

The exact `Invalid polygon coordinate.` producer was `core/polygon_transport.py::_parse_polygon_coordinates`. It collapsed non-finite vertices into a generic `ValueError` without recording the vertex, CRS, or validation rule. No longitude/latitude magnitude check exists in the Phase 32K source tree.

The confirmed upstream defect was in `core/ept_spatial_reference.py::resolve_ept_spatial_reference`. It evaluated WKT before the explicit EPT authority/code and `_guess_geographic` searched the entire WKT for `GEOGCS` before considering `PROJCS`. The live EPT therefore produced a contradictory valid spatial reference:

- empty authority and authid
- `geographic = true`
- `projected = false`
- units `metre`
- top-level `PROJCS` WKT ending in `AUTHORITY["EPSG","6635"]`

The same raw CRS WKT was propagated independently through repository, polygon, query, clipping, processing, and output fields. Backend polygon transport also labeled already-transformed EPSG:6635 geometry with the original EPSG:3750 processing CRS and original envelope.

## Corrected contract

Explicit EPT `authority = EPSG` and `horizontal = 6635` now canonicalize first to `EPSG:6635`; WKT and PROJJSON are retained as evidence. Top-level `PROJCS`/`PROJCRS` is projected even when it contains a nested `GEOGCS`/`BASEGEOGCRS`. A spatial reference cannot be both geographic and projected.

The shared polygon parser now applies:

- every CRS: exactly two numeric XY values and finite-number validation;
- geographic CRS: longitude `-180..180` and latitude `-90..90`;
- projected CRS: finite values without degree-domain magnitude checks;
- unknown CRS: conservative finite-number validation without invented semantics.

Failures report the coordinate, vertex index, source CRS, destination CRS, projected/geographic classification, and rule (`FINITE_COORDINATE_REQUIRED` or `GEOGRAPHIC_LONGITUDE_LATITUDE_RANGE`). Geometry parsing and coordinate-domain failures remain distinct.

Prerun bounds derivation and backend polygon transport use the same validator. Transformed transport now records the destination CRS and derives its envelope from the transformed vertices.

## Real evidence

The preserved Phase 32K polygon and exact EPT metadata were run through the managed PBM Python environment. Network credentials were unavailable to the sandboxed child, so the unmodified 7,915-byte `ept.json` was copied locally for this metadata-only spatial gate; no EPT point data was copied or read.

Result:

- polygon source CRS: `EPSG:3750`
- repository, processing, query, and transport CRS: `EPSG:6635`
- repository classification: projected `true`, geographic `false`, units `metre`
- transformed bounds: `196188.631177, 2167079.3494, 214143.018468, 2180976.39619`
- selected logical EPT sources: 1
- spatial blockers: 0
- backend transport vertex count: 106

The exact coordinate set passes both source selection and backend transport validation. Regression fixtures also retain strict rejection of `181,20` under EPSG:4326, accept `-155,19`, accept large EPSG:6635/EPSG:32605 values, and reject NaN/Inf.

## Managed child environment

The Phase 32K child launcher already calls `build_processing_engine_environment`. A live isolated child initialized GDAL 3.9.3, PROJ 9.5.1, and EPSG:6635 as projected with:

- `GDAL_DATA = <backend>/env/Library/share/gdal`
- `PROJ_DATA` and `PROJ_LIB = <backend>/env/Library/share/proj`
- `<backend>/env/Library/bin` on `PATH`

The earlier `gdalvrt.xsd` failure is not reproduced under the canonical child environment. Focused regression coverage verifies these resources and DLL paths.

## Phase 32K preservation

This phase does not change bounded EPT reads, 100 m child cores, 50 m halos, pilot/HAG strategy, the 109-parent scheduler, checkpoint recovery, CHM science, or external-worker policy.

## Packaged QGIS and scientific evidence

The validated ZIP was installed into the idle default profile and run with QGIS 3.44.13-Solothurn. Mission Control opened without an exception. The preserved EPSG:3750 polygon Detailed Check reported Engine READY, Plan ready, Spatial Ready, CHM selected, one logical EPT source, and no blockers. Its transformed bounds matched the managed-runtime probe exactly.

The authoritative repair/reload transaction refreshed the stale setup marker without reinstalling backend packages, after which the actual Processing Engine reported READY.

A 100 m square over the same real UNC EPT source completed end to end:

- source/query/output CRS: `EPSG:6635`
- exact bounds: `196500, 2167500, 196600, 2167600`
- CHM size: 100 by 100 cells at 1 m
- valid pixels: 100 percent; range `0..37.808812105511`
- final GeoTIFF SHA256: `d6feb27f51da3f697cbaf4ecc31efb2f60600db03b5f948f254a8a7fa06a897f`
- exact-mask/finalization result: completed
- output registration: completed
- QGIS raster validity: true; loaded layer count: 1

The existing Phase 32K four-parent checkpoint and restart evidence remains valid and its execution code was not changed. The full 109-parent large job was not rerun during this CRS-only phase.
