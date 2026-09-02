# Phase 32T UI Freeze Profile

## Root cause

The Process page connected every product checkbox to three synchronous callbacks. The session callback called `_publish_session_state()`, which normalized the selected polygon and hashed its complete WKT on the QGIS GUI thread. Toggle latency therefore scaled with feature count and geometry complexity. FHD was not running PyForestScan during selection; it exposed this generic product-toggle defect.

## Corrected signal contract

Product selection now performs only these operations:

1. Mark the Prerun report stale.
2. Update contextual parameter visibility and button readiness.
3. Update concise Prerun text.
4. Publish selected product names by replacing the cached semantic session state.

It does not normalize polygons, inspect EPT, traverse files, verify PBM, import scientific libraries, calculate workload, or refresh repository state. Expensive planning remains in background Prerun execution.

## Measured QGIS 3.44.13 result

With polygon normalization instrumented as a 250 ms forbidden operation:

- 20 FHD on/off toggles: mean 0.19 ms, maximum 0.90 ms.
- Rapid CHM/FHD/PAI/PAD/Rumple toggles: maximum 0.16 ms.
- Polygon normalization calls from toggles: 0.

The result is independent of source and polygon scale because the callback no longer reads either one.

## Layout measurements

The Phase 32R/32S Process content minimum-height baseline was 1574 px. The responsive Phase 32T two-column workspace measured 891 px at normal/wide width, a 43.4% reduction. It uses one column below 620 px and two columns at or above that measured breakpoint. QGIS tests at 420, 600, 760, and 1100 px reported zero horizontal overflow.

## Scientific import audit

Mission Control constructs product controls from a static release registry. It does not import NumPy, SciPy, PDAL, GDAL, Rasterio, or PyForestScan and makes no network request. Scientific imports remain inside the managed Processing Engine execution boundary.
