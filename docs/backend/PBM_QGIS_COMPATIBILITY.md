# PBM QGIS Compatibility

Phase 22B adds a QGIS compatibility report used by Mission Control Settings and by future PBM installer decisions. The report is defensive: it can run inside QGIS, and the module can also be imported by plain-Python tests without QGIS installed.

## Reported Fields

The compatibility report includes:

- QGIS version.
- QGIS major version.
- Python version.
- Qt version when available.
- Platform string.
- Plugin API availability.
- Processing provider registration compatibility.
- Settings API availability.
- QGIS message log availability.
- Known warnings.

## Supported Target

QGIS 3.x is the current supported target for internal QA. The compatibility layer is designed for current stable and LTR QGIS 3.x builds.

QGIS 4.x checks are defensive only. The layer parses QGIS 4.x version strings, avoids assuming identical APIs, and reports a warning that QGIS 4.x must be tested when available.

## Failure Behavior

If QGIS APIs are unavailable, the compatibility report does not crash. It reports clear warnings such as missing QGIS Python API, missing Qt settings access, or missing Processing provider registration APIs.

PBM does not use compatibility checks to modify QGIS Python or system settings. The checks are read-only readiness signals for users and future installer phases.
