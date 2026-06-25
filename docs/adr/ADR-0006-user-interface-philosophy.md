# ADR-0006: User Interface Philosophy

## Status

Accepted

## Context

QGIS users need guided workflows, but scientific processing must remain
reproducible and compatible with QGIS automation.

## Decision

The plugin will prioritize QGIS Processing algorithms as the primary user
interface. Custom GUI elements may be added later for dependency diagnostics,
workflow guidance, or visualization support, but they should not replace
Processing as the authoritative execution path.

## Consequences

- Users benefit from Processing history, batch tools, and Model Builder.
- Documentation can focus on repeatable algorithm workflows.
- GUI work remains optional and justified by user needs.

