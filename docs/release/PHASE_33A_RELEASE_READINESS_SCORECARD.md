# Phase 33A Release Readiness Scorecard

## Decision

**BETA_WITH_BLOCKERS.** `0.2.0-beta.1` is appropriate for controlled beta testing. It is not ready for RC1 because fresh full-workflow and long-job evidence is incomplete and Micromamba bootstrap artifacts are not pinned.

Scores use 0-5, where 5 means the release gate has current installed-product evidence.

| Category | Score | Evidence | Open gate |
| --- | ---: | --- | --- |
| Scientific correctness | 4 | upstream contract, product tests, established CHM SHA | fresh final-package products |
| Processing reliability | 3 | durable coordinator/checkpoint tests | long job and injected failures |
| Performance | 3 | measured EPT baseline, conservative policy | fresh local/network matrix |
| UI/UX | 4 | QGIS 3.44/4.0 lifecycle and grouping matrices | visible human review |
| Help/documentation | 4 | 84/84 default-state controls | conditional-state review |
| State consistency | 4 | attempt/current-job tests | fresh second unrelated job |
| Error handling | 3 | durable taxonomy/diagnostics | failure injection |
| Installation | 3 | ZIP/replacement simulation | clean engine install/repair/update |
| Packaging | 5 | deterministic package and parity gates | none identified |
| Windows compatibility | 4 | QGIS 3.44.13 UI and historical science | final workflow repetition |
| QGIS 4 compatibility | 2 | QGIS 4.0.0 UI lifecycle/control audit | engine/provider/science |
| Linux | 1 | QGIS-free tests/spec only | native qualification |
| macOS | 1 | platform mapping/spec only | native qualification |
| Security/data safety | 4 | isolated runtime, owned paths, no supported `shell=True` | formal threat review |
| Recovery | 3 | checkpoint/finalization tests | restart/failure injection |
| Long-job behavior | 3 | historical EPT evidence | fresh substantial job |

## Blockers

### P0 Release Blockers

No new P0 defect was demonstrated by the fresh automated or installed-package UI checks.

### P1 RC Blockers

- Complete the LAS/LAZ/COPC/EPT, Folder/Polygon, and all-product matrix on the final package.
- Run a substantial real job and observe progress, ETA, pause, resume, cancel, recovery, and registration.
- Execute safe failure injection and a second unrelated job in the same session.
- Verify clean Windows engine install, damaged repair, outdated update, and READY handoff.
- Pin Micromamba URLs/SHA-256 and produce reproducible supported-platform runtime locks.
- Repeat the exact CHM canary from the final clean installed package.

### P2 Post-RC

- Qualify current QGIS 4.x beyond UI construction.
- Complete native Linux and macOS engine/science qualification.
- Move any remaining recoverable internals out of final-output folders where observed.

### P3 Future

Point-cloud viewer/editor, AI segmentation, automatic COPC conversion, and richer history UX.

## Fresh Evidence

- QGIS 3.44.13: clean extracted starting ZIP, 100 construction/unload cycles, 100 navigation/state cycles, four engine states, and 420-800 px geometry, PASS.
- QGIS 4.0.0: same installed-package lifecycle matrix after correcting the Qt 6 audit harness, PASS.
- Both runtimes: 84 visible default-state controls, 100% semantic help/accessibility coverage, zero generic phrases.
- QGIS-free suite at audit start: 992 passed, 7 skipped.

No fresh real LiDAR processing, engine installation, screenshot-based human review, long job, or failure injection was completed. Historical reports are supporting context, not fresh evidence.

## Mandatory Matrix

| Area | Items | Phase 33A status |
| --- | --- | --- |
| Sources | LAS / LAZ / COPC / EPT | NOT TESTED fresh |
| Modes | Folder / Polygon | NOT TESTED fresh end-to-end |
| Products | CHM / DTM / PAD / PAI / FHD / Canopy Cover / Rumple / Point Density | contracts PASS; real outputs NOT TESTED fresh |
| Controls | Prerun / Process / Pause / Resume / Cancel / Recovery / Results loading | contracts PASS; live workflow NOT TESTED fresh |
| Spatial | same / differing / unknown / fallback CRS | automated matrix PASS; live data NOT TESTED fresh |
| Sizes | small / medium / large | historical only; NOT TESTED fresh |
| Platform | Windows QGIS 3.44.13 | UI PASS; final science workflow NOT TESTED |
| Platform | Windows QGIS 4.0.0 | UI PASS; engine/science NOT TESTED |
| Platform | Linux / macOS | NOT TESTED |
