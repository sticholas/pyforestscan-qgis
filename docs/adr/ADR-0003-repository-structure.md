# ADR-0003: Repository Structure

## Status

Accepted

## Context

The repository needs to support QGIS plugin packaging, scientific workflow code,
documentation, tests, sample data, and release automation without mixing
responsibilities.

## Decision

The repository will use a top-level `pyforestscan_qgis/` plugin package with
subdirectories for algorithms, core services, Processing integration, resources,
styles, and icons. Tests, sample data, scripts, and docs will remain top-level
repository concerns.

## Consequences

- The future plugin package has a clear boundary.
- Test and documentation assets are not confused with installable plugin code.
- Every directory must carry documentation for its purpose.

