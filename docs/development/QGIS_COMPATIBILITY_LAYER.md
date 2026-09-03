# QGIS Compatibility Layer

`pyforestscan_qgis/core/qgis_compat.py` centralizes defensive QGIS runtime checks and wrappers used by PyForestScan QGIS.

## Goals

- Keep compatibility checks importable in plain Python.
- Detect QGIS, Python, Qt, platform, Processing provider, settings, and message-log availability.
- Support QGIS 3.x as the current target.
- Prepare for QGIS 4.x without assuming APIs are identical.
- Fail gracefully with clear messages when APIs are unavailable.

## Safe Wrappers

The module provides wrappers for:

- Adding raster layers.
- Adding vector or table layers.
- Opening and raising Mission Control.
- Registering and unregistering the Processing provider.
- Accessing QGIS settings.
- Reporting messages to the QGIS log.

Each wrapper returns a structured result with `success`, `message`, and optional object reference. Wrappers should not raise user-facing crashes when QGIS APIs are missing or different.

## Development Rules

- Do not import QGIS modules at module import time in `qgis_compat.py`.
- Keep version parsing testable without QGIS.
- Treat QGIS 4.x as unverified until tested against real builds.
- Resolve Qt enum differences through `compat/qt.py`; do not spread QGIS-version
  conditionals through Mission Control pages.
- Do not use compatibility checks to alter QGIS Python, QGIS install folders, or user environment variables.

## Phase 32X Evidence

QGIS 3.44.13 LTR with Qt 5.15.13 passed live Mission Control construction and
the scientific-settings sizing matrix. A local QGIS 4.0.0 Qt 6 spike reached
Mission Control dock construction after scoped-enum compatibility repairs, but
the full interaction harness did not finish. QGIS 4.2.1 remains untested and
QGIS 4 support therefore remains unqualified.
