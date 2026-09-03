# Phase 32Y Release Hardening

Phase 32Y is a focused scientific-UX and release-evidence pass. It does not
change PyForestScan calculations, adaptive processing, PBM transactions, or
Advanced Toolbox algorithms.

## Scientific controls

Advanced Scientific Settings uses semantic groups and shared settings first.
At wide Process-page widths it balances groups across two form columns; narrow
widths use one column and wrapped rows. Hidden product controls contribute no
height. The QGIS 3.44.13 live matrix measured collapsed height 28 px, CHM 103
px, CHM + FHD 183 px, CHM + PAD 174 px, CHM + FHD + PAD 219 px, and all
products 370 px, with no horizontal overflow.

The external action is **PyForestScan Calculation Guide ↗** and opens the
[official calculation documentation](https://pyforestscan.sefa.ai/api/calculate/).

## Processing-area ownership

Selecting a layer is not the same as adopting a processing area. BatchPage now
publishes only an explicitly adopted selection. Refreshing or changing the
layer, source mode, or workflow clears that ownership. The initial summary is:

`Selection: Not selected   Area: Not selected   Geometry: Not selected   Processing Area CRS: Not selected`

QGIS feature area is measured by `QgsDistanceArea` using the source CRS,
project transform context, and WGS84 ellipsoid, then converted from square
metres to hectares. Raw EPSG:4326 square degrees are never converted directly.
The existing authoritative transform pipeline still owns processing geometry.

## Guided actions

Only the next useful action receives the primary role: install or repair the
Processing Engine, choose LiDAR, adopt an area when polygon mode requires it,
run Prerun Check, or process. Tools & Setup uses Install, Repair,
Reinstall/Repair, and Update wording according to engine state. When the engine
is ready but no source is selected, the global status is **Ready for input**,
not **Needs setup**.

Preferences are ordered Default Output Folder, Fallback CRS, then Startup.

## Compatibility evidence

On 2026-09-03, official QGIS releases were 3.44.14 LTR and 4.2.2 stable. The
available host ran QGIS 3.44.13 with Qt 5.15.13. The clean extracted package
constructed Mission Control, detected plugin/provider APIs, produced the full
scientific sizing matrix, resolved contextual help, and showed clean initial
area state. QGIS 4.0 construction evidence from Phase 32X remains a spike only.

QGIS 4.2.2, macOS, and native Linux GUI/engine tests were unavailable and are
NOT TESTED. Platform YAML files remain solve specifications, not exact locks.
Micromamba still uses an unpinned `latest` archive with no trusted archive
SHA-256 values. These are RC portability blockers; no hashes or support claims
were inferred.

## Release gates

- Repeat package and science QA on current QGIS 3.44.14.
- Complete isolated QGIS 4.2.2 load, navigation, provider, engine, CRS, Prerun,
  CHM, Results, unload, and reload tests.
- Produce and validate exact win-64, linux-64, osx-arm64, and viable osx-64
  environment locks.
- Pin exact Micromamba archive URLs, versions, and archive SHA-256 values.
- Execute real macOS Apple Silicon and Linux platform gates.
- Preserve the established deterministic CHM canary.
