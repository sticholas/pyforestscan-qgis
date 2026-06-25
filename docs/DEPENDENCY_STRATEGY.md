# Dependency Strategy

The plugin must treat PyForestScan as an external computational dependency, not
as vendored code.

## Principles

- Do not vendor PyForestScan into the plugin repository.
- Depend only on public PyForestScan APIs.
- Isolate PyForestScan calls behind plugin-owned adapter boundaries.
- Document dependency expectations separately from plugin code.
- Do not install dependencies automatically without explicit user action.

## Expected Runtime Dependencies

The eventual plugin is expected to need:

- QGIS and its Python environment.
- PyQt and QGIS Python APIs provided by QGIS.
- PyForestScan.
- PyForestScan transitive scientific and geospatial dependencies.

Specific version ranges must be confirmed during implementation and release
testing.

## Optional Dependencies

Optional dependencies may support advanced exports, reports, visualization, or
performance. Optional dependencies must not prevent basic plugin loading.

## Environment Validation

The plugin includes an Environment Check Processing algorithm that reports:

- QGIS Python executable path.
- Python version used by QGIS.
- Platform and operating system.
- QGIS version when available.
- Plugin path.
- PyForestScan availability and version when available.
- PDAL Python binding availability and version when available.
- GDAL Python binding availability and version when available.
- rasterio availability and version when available.
- numpy availability and version when available.
- Final readiness: READY, PARTIALLY READY, or NOT READY.

Missing scientific dependencies are reported as FAIL with guidance and must
not crash plugin execution. Uncertain metadata, such as an importable package
with an unknown version, is reported as WARNING. The validator never installs
packages or modifies the user environment.

## Windows Dependency Policy

On Windows QGIS, the plugin must treat QGIS Python as separate from
system Python and WSL Python. Do not automatically install packages. Prefer
OSGeo4W-managed packages for compiled dependencies such as PDAL, GDAL,
rasterio, numpy, pyproj, shapely, pandas, scipy, and related geospatial
libraries. Use pip only for packages that are not available through
OSGeo4W, and avoid allowing pip to upgrade or replace OSGeo4W-managed
compiled packages.

For QGIS 3.44.x on this machine, OSGeo4W provides `python3-pdal`; QGIS
already includes the PDAL command-line runtime, but the Python `pdal`
binding must be installed separately.
Install and verify that binding in the same QGIS root reported by the
plugin Environment Check, because side-by-side QGIS installs do not
share Python package directories.

## Verified Development Baseline

The current verified Windows/QGIS development baseline is QGIS
`3.44.11-Solothurn` with Python `3.12.13`, PyForestScan `0.4.0`, PDAL Python
bindings `3.5.3`, GDAL `3.13.1`, rasterio `1.5.0`, and numpy `2.4.6`. Use this
as the initial environment for PyForestScan API discovery. Future releases must
still define explicit supported version ranges through testing.

## Packaging Position

The QGIS Plugin Repository package should remain lightweight. Scientific Python
dependencies should be handled through documented installation strategies for
the user's platform and QGIS distribution.

