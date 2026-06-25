# Contributing Guide

## Engineering Standards

Recommended baseline:

- Python formatting: `ruff format`.
- Linting: `ruff check`.
- Testing: `pytest`.
- Type clarity: type hints for new core code where practical.
- Documentation: update docs and ADRs when behavior or architecture changes.

## Branch Strategy

- `main`: stable release history.
- `develop`: integration branch for upcoming work.
- `feature/<topic>`: focused feature branches.
- `fix/<topic>`: focused bug fix branches.
- `release/<version>`: release preparation branches when needed.

## Versioning Strategy

Use semantic versioning after the first public release:

- MAJOR for incompatible workflow or API changes.
- MINOR for new plugin functionality.
- PATCH for bug fixes and documentation-only release corrections.

Before `1.0.0`, minor versions may introduce breaking changes if they are
clearly documented.

## Pull Request Expectations

- Explain user impact.
- Explain scientific or architectural assumptions.
- Link issues or ADRs when relevant.
- Include tests for implemented behavior.
- Include documentation for user-facing changes.

## Continuous Integration

CI should eventually include:

- Formatting checks.
- Lint checks.
- Unit tests.
- Documentation link checks.
- QGIS integration tests where infrastructure allows.
- Release packaging validation.

## Adapter Development Rules

- Keep Processing algorithms thin; put PyForestScan and PDAL integration behind
  `PyForestScanAdapter`.
- Do not return public dictionaries from core adapter APIs; add typed dataclasses
  or enums in `pyforestscan_qgis/core/types.py`.
- Use immutable dataclasses for configuration and request objects.
- Raise plugin-owned exceptions from `pyforestscan_qgis/core/exceptions.py` at
  the adapter boundary.
- Use structured log records and progress snapshots instead of `print()`.
- Add plain-Python unit tests for core behavior before adding QGIS integration
  tests.
