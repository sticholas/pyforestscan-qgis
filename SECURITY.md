# Security Policy

PyForestScan QGIS is a desktop QGIS plugin that processes local LiDAR, raster, vector, and report files. Security work focuses on safe file handling, dependency hygiene, predictable output locations, and protecting QGIS from unsafe execution modes.

## Supported Versions

The current internal release line on `develop` is supported for project testers. Public support windows will be defined when the project publishes tagged public releases.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the maintainers instead of opening a public issue. Include:

- Affected commit, release, or ZIP package.
- Operating system and QGIS version.
- PyForestScan, PDAL, GDAL, rasterio, and numpy versions if relevant.
- Steps to reproduce.
- Example input files only when safe to share.
- Impact and suggested mitigation, if known.

## Security Principles

- Treat LiDAR, raster, vector, CSV, HTML, JSON, and workspace files as untrusted input.
- Do not execute user-provided scripts.
- Write only under user-selected output locations.
- Keep external worker mode disabled until a safe headless launcher is proven.
- Do not use QGIS GUI executables as background worker Python.
- Avoid automatic dependency installation from inside the plugin.
- Prefer clear local error messages without leaking sensitive paths into public reports.
- Preserve reproducibility metadata while respecting data privacy.

## Data Privacy

The plugin is local-first and does not upload data, create cloud accounts, or sync workspaces. Users are still responsible for protecting sensitive site locations, file paths, and ecological survey data when sharing reports, logs, screenshots, or issue attachments.
