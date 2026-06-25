# ADR-0005: Testing Strategy

## Status

Accepted

## Context

The plugin will combine QGIS integration, scientific processing workflows, and
dependency-sensitive behavior.

## Decision

Testing will be layered. Core logic should be unit tested with `pytest`.
Processing integration should be tested with QGIS-aware tools where feasible.
Scientific product tests should use small, redistributable sample data and
known expected outputs.

## Consequences

- Core services should remain independent enough to test outside QGIS.
- QGIS integration tests may run in a specialized CI job or release workflow.
- Sample data must be curated carefully to avoid large repository growth.

