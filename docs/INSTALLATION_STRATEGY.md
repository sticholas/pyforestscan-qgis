# Installation Strategy

The installation strategy must respect the complexity of QGIS Python
environments and geospatial scientific dependencies.

## Planned Installation Paths

- QGIS Plugin Repository for the plugin package.
- Documented PyForestScan installation instructions for the active QGIS Python
  environment.
- Platform-specific notes for Windows, macOS, and Linux.

## Non-Goals

- Automatically modifying a user's Python environment without consent.
- Bundling large binary dependencies into the plugin package.
- Assuming that system Python and QGIS Python are the same environment.

## Environment Check Workflow

Before running future PyForestScan-backed algorithms, users should run the
`Environment Check` algorithm from the PyForestScan Processing provider. The
report identifies the active QGIS Python executable, operating system, plugin
path, QGIS version when available, and import status for PyForestScan, PDAL,
GDAL, rasterio, and numpy.

The plugin only reports diagnostics. It does not install packages, invoke package
managers, or modify the QGIS Python environment. Missing dependencies should be
installed by the user or administrator using the installation method appropriate
for the active QGIS distribution.

## Windows QGIS 3.44 Dependency Strategy

For Windows QGIS 3.44.x, use the QGIS/OSGeo4W Python environment, not
system Python or WSL Python. Compiled geospatial dependencies should come
from OSGeo4W whenever available. The documented recommended route is to
install `python3-pdal` through the OSGeo4W/QGIS setup tool, verify
`import pdal`, and then install `pyforestscan` into QGIS Python with
`python3 -m pip install --no-deps pyforestscan` only after dependencies
are satisfied.

See [Windows QGIS Dependencies](development/WINDOWS_QGIS_DEPENDENCIES.md)
for exact inspection commands, risks, and troubleshooting. Command-line
verification must use the same QGIS install path shown by the plugin
`Environment Check`; each QGIS install has its own OSGeo4W Python
environment and package database.

## Future Documentation Requirements

Installation documentation should include:

- Supported QGIS versions.
- Supported operating systems.
- How to identify the QGIS Python executable.
- How to install PyForestScan into that environment.
- How to run the plugin environment validator.
- Common failure modes and fixes.

