# Compatibility

PyForestScan QGIS supports only the combinations listed as tested here. A
recognized platform is not automatically a supported Processing Engine target.

Official QGIS release information checked on 2026-09-03 lists QGIS 3.44.14
Solothurn as the LTR and QGIS 4.2.2 Belem do Para as the current release.
QGIS 4 uses Qt 6; QGIS 3.44 LTR uses Qt 5.

## Support tiers

- SUPPORTED: plugin, Processing Engine, and science evidence passed.
- SUPPORTED WITH LIMITATIONS: the tested chain passed with documented scope.
- UI-COMPATIBLE: plugin/UI matrix passed; engine/science chain is incomplete.
- EXPERIMENTAL: partial or QGIS-free evidence only.
- NOT TESTED: recognized target without executable evidence.
- UNSUPPORTED: outside current product scope or blocked by known constraints.

| OS | Architecture | QGIS | Qt | Plugin UI | Processing Engine | Science canary | Status | Test date | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Windows | x86_64 | 3.34.x | Qt 5 | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | - | Official release/API generation investigated; no runnable 3.34 installation was available. |
| Windows | x86_64 | 3.40.x | Qt 5 | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | 2026-09-03 | Local 3.40.5/3.40.15 directories contain setup stubs only, not a runnable QGIS application. |
| Windows | x86_64 | 3.44.13 | Qt 5.15.13 | PASS | PASS | PASS | SUPPORTED WITH LIMITATIONS | 2026-09-03 | Phase 32Z 24-case scientific UI matrix passed; established Windows CHM canary remains exact. Current 3.44.14 still needs repetition. |
| Windows | x86_64 | 4.0.0 | Qt 6 | PASS | NOT TESTED | NOT TESTED | UI-COMPATIBLE | 2026-09-03 | Isolated 24-case Mission Control scientific matrix passed with no empty groups, overflow, or value migration. Full Prerun/engine/science/unload gate remains open. |
| Windows | x86_64 | 4.2.2 | Qt 6 | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | - | Current stable build was not installed on the test host. |
| macOS | Apple Silicon | current 3.x/4.x | Qt 5/6 | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | - | Native fonts, notarization, engine install/repair, and science remain open. |
| macOS | Intel | current 3.x/4.x | Qt 5/6 | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | - | Viability depends on current upstream package availability. |
| Linux | x86_64 | current 3.x/4.x | Qt 5/6 | EXPERIMENTAL | NOT TESTED | NOT TESTED | EXPERIMENTAL | 2026-09-03 | QGIS-free tests pass; native QGIS and engine gates were unavailable. |
| Linux | ARM64 | current | varies | EXPERIMENTAL | NOT TESTED | NOT TESTED | EXPERIMENTAL | 2026-09-03 | Platform mapping only. |
| Linux Flatpak | any | any | varies | NOT TESTED | UNSUPPORTED | NOT TESTED | UNSUPPORTED | - | Sandbox filesystem and subprocess behavior need a dedicated design. |
| BSD | any | any | varies | EXPERIMENTAL | UNSUPPORTED | NOT TESTED | UNSUPPORTED | - | Not a first-release target. |

QField and mobile QGIS are outside the desktop Mission Control scope.

## QGIS and Qt boundary

`core/qgis_compat.py` owns guarded QGIS operations and version reporting.
Application code imports Qt through `qgis.PyQt`; no direct PyQt5 dependency is
used. `compat/qt.py` resolves Qt 5 unscoped and Qt 6 scoped enums at the UI
boundary. A local QGIS 4.0.0 spike exposed and repaired dock-area, dock-feature,
size-policy, frame, form-layout, cursor, focus, and keyboard enum differences.
Phase 32Z promoted QGIS 4.0 from a construction spike to UI-COMPATIBLE after an
isolated 24-case scientific-layout matrix. QGIS 4 remains unqualified for
engine/science support until Processing
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

Phase 32Z attempted isolated Micromamba 2.8.1 dry-run solves for `win-64`,
`linux-64`, `osx-arm64`, and `osx-64`. Resolution did not complete within the
bounded test window and was stopped without creating an environment. This is
an attempted test, not lock or engine-install evidence.

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

The supported release matrix is currently Windows QGIS 3.44.x only. QGIS 4.0
is UI-COMPATIBLE, not fully supported. Expanding support requires real QGIS
4.2, macOS Apple Silicon, and Linux runners or manual gates; QGIS-free unit
tests alone do not promote a target to supported.

Sources: [QGIS Download](https://qgis.org/download/), [QGIS Installation
Guide](https://qgis.org/resources/installation-guide/), and the [official
PyForestScan calculation reference](https://pyforestscan.sefa.ai/api/calculate/).
