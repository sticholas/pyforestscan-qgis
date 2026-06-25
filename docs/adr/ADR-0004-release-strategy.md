# ADR-0004: Release Strategy

## Status

Accepted

## Context

The plugin may eventually be submitted to the official QGIS Plugin Repository
and should provide reproducible scientific workflows.

## Decision

The project will use semantic versioning after public releases begin, maintain a
changelog, document supported QGIS and PyForestScan versions, and use release
branches when stabilization is needed.

## Consequences

- Users can reason about compatibility and upgrade impact.
- Release candidates need documented test evidence.
- Packaging checks become part of release acceptance.

