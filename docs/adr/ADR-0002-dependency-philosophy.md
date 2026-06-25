# ADR-0002: Dependency Philosophy

## Status

Accepted

## Context

QGIS plugins run inside QGIS-managed Python environments. PyForestScan and its
scientific dependencies may evolve independently and may include geospatial
packages that are difficult to bundle safely.

## Decision

The plugin will not vendor PyForestScan or automatically install scientific
dependencies. It will document expected dependencies, validate the active
environment, and depend on stable public PyForestScan APIs through a small
plugin-owned adapter boundary.

## Consequences

- The plugin package remains lightweight.
- Users receive explicit installation guidance.
- Dependency errors can be surfaced before long-running processing begins.
- Release testing must include dependency compatibility checks.

