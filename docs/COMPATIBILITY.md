# Compatibility

PyForestScan QGIS supports only the combinations listed as tested here. A
recognized platform is not automatically a supported Processing Engine target.

Official QGIS release information checked on 2026-09-03 lists QGIS 3.44.14
Solothurn as the LTR and QGIS 4.2.2 Belem do Para as the current release.
QGIS 4 uses Qt 6; QGIS 3.44 LTR uses Qt 5.

## Support tiers

- Tier 1: current QGIS LTR after plugin, engine, science, and package QA.
- Tier 1: current stable QGIS after the same QA has passed.
- Tier 2: previous LTR where technically feasible and explicitly tested.
- Unqualified: recognized or planned combinations without complete evidence.

| OS | Architecture | QGIS | Plugin | Processing Engine | Tested | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Windows | x86_64 | 3.44.13 LTR | SUPPORTED WITH LIMITATIONS | SUPPORTED WITH LIMITATIONS | 2026-09-03 | Phase 32Y live Mission Control/package QA passed on the installed prior point release; current 3.44.14 remains to be repeated. |
| Windows | x86_64 | 4.2.2 | NOT TESTED | NOT TESTED | Not tested | Current stable Qt 6 build needs complete live QA. |
| Windows | x86_64 | 4.0.0 | Unqualified spike | Unqualified | 2026-09-03 | Mission Control construction reached the live dock path after scoped-enum repairs; a full interaction run did not complete. |
| macOS | Intel | current LTR/stable | NOT TESTED | NOT TESTED | Not tested | Package solve, subprocess, permissions, and Gatekeeper behavior remain open. |
| macOS | Apple Silicon | current LTR/stable | NOT TESTED | NOT TESTED | Not tested | `osx-arm64` is recognized; no engine lock or live test exists. |
| Linux | x86_64 | current LTR/stable | EXPERIMENTAL | EXPERIMENTAL | QGIS-free core only | Native-package QGIS needs live plugin/engine QA. |
| Linux | ARM64 | current LTR/stable | EXPERIMENTAL | NOT TESTED | QGIS-free mapping only | Dependency solve and QGIS availability are unverified. |
| Linux Flatpak | any | any | UNSUPPORTED | UNSUPPORTED | Not tested | Sandbox filesystem and subprocess rules require a dedicated design. |
| BSD | any | any | EXPERIMENTAL | UNSUPPORTED | Not tested | Not a first-release target. |

QField and mobile QGIS are outside the desktop Mission Control scope.

## QGIS and Qt boundary

`core/qgis_compat.py` owns guarded QGIS operations and version reporting.
Application code imports Qt through `qgis.PyQt`; no direct PyQt5 dependency is
used. `compat/qt.py` resolves Qt 5 unscoped and Qt 6 scoped enums at the UI
boundary. A local QGIS 4.0.0 spike exposed and repaired dock-area, dock-feature,
size-policy, frame, form-layout, cursor, focus, and keyboard enum differences.
That spike is compatibility evidence, not a support claim. QGIS 4 remains
unqualified until Mission Control construction, Processing
provider registration, settings, layer loading, tasks/signals, CRS selection,
engine verification, and a deterministic science canary pass on a real build.
`metadata.txt` declares QGIS 3.28 as the minimum and intentionally has no
maximum; this is an installability declaration, not evidence that every newer
QGIS release is supported.

## Managed runtime inventory

`backend_manifest.json` and `backend_specs/environment*.yml` are the authority.
The current recipe owns Python 3.12, PyForestScan 0.4.x from PyPI, and the
conda-forge scientific stack: PDAL and python-pdal, GDAL/libgdal, Rasterio,
NumPy, SciPy, pandas, Shapely, pyproj, Fiona, GeoPandas, Matplotlib, tqdm, and
pip. PyForestScan product execution and point-cloud I/O use managed PDAL;
QGIS Processing PDAL algorithms are a separate optional toolbox surface.

The platform YAML files are solve specifications, not lock files. Windows
x86_64 is the only installer-qualified target. Micromamba is still selected as
`latest` and the manifest SHA-256 entries are empty. Release support for any
additional platform, and a production RC, require a fixed artifact version,
archive SHA-256 values verified against the exact downloaded bytes, and
platform-specific solved locks. The installer must fail closed when a release
requires a checksum that is absent.

## Process policy

Backend paths are built with `pathlib`. The user-local root is LocalAppData on
Windows, Application Support on macOS, and XDG-style local data on Linux.
Managed subprocesses receive a sanitized environment. Windows children use
hidden-console flags; POSIX detached coordinators use a new process session.
Owned-tree cancellation uses `taskkill /T` on Windows and process-group signals
on POSIX. No path modifies QGIS Python, system Python, global PATH, or shell
profiles.

## Test strategy

- CORE: pure Python on Windows, Linux, and macOS.
- PLUGIN: construct Mission Control and register the provider in real QGIS.
- ENGINE: install/repair/verify each supported architecture from pinned locks.
- SCIENCE: deterministic product fixtures, including the CHM canary.
- PACKAGE: ZIP validation, source-to-ZIP parity, and clean-profile install.
- LIVE: release-gate QGIS interaction, cancellation, loading, and long-job QA.

CI should eventually cover Windows, Linux, and macOS against current LTR and
stable QGIS where runners are practical. New QGIS releases trigger a Qt/API
audit and package/engine/science smoke before support is declared.

The executable release matrix is currently Windows QGIS 3.44.x only. Expanding
it requires real QGIS 4.2, macOS Apple Silicon, and Linux runners or manual
gates; QGIS-free unit tests alone do not promote a target to supported.

Sources: [QGIS Download](https://qgis.org/download/), [QGIS Installation
Guide](https://qgis.org/resources/installation-guide/), and the [official
PyForestScan calculation reference](https://pyforestscan.sefa.ai/api/calculate/).
