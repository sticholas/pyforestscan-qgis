# ADR-0001: Processing Provider Architecture

## Status

Accepted

## Context

The plugin must expose PyForestScan capabilities to QGIS users in a way that is
discoverable, scriptable, and compatible with QGIS Processing history and Model
Builder.

## Decision

The plugin will use a QGIS Processing provider as the primary interface for
scientific workflows. Individual products will be implemented as Processing
algorithms, with shared validation and support code located in plugin core
modules.

## Consequences

- Workflows can be run from the Processing Toolbox, Model Builder, and QGIS
  Python automation.
- Algorithm classes must remain focused on QGIS parameter handling, feedback,
  cancellation, and output registration.
- Custom GUI work is deferred until a clear need exists beyond Processing.

