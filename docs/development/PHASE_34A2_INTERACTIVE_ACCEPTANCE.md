# Phase 34A2 Interactive Acceptance

Date: 2026-09-08. Recovered baseline: `734bc8633a779beb3e919818e9373b1ede609f91`,
branch `develop`. Work remains uncommitted. No reset, cleanup, or loss of
recovered assets occurred. This is an evidence checkpoint, not phase completion.

Release state: **INTERACTIVE_VIEWER_EXPERIMENTAL**.

## Failure Diagnosis

The original exit code 1 was reproduced as a harness lifetime error:
`RuntimeError: wrapped C/C++ object of type ViewerWorker has been deleted`.
The harness queried `isRunning()` after Qt deleted the completed worker.
Python-owned completion events now survive Qt object deletion. The reproducer
subsequently exited 0.

Additional independently observed defects were fixed:

- Repeated QtQuick framebuffer captures were associated with Chromium D3D
  shared-image/context-loss errors. Captures now come from the WebGL canvas,
  after an explicit render, without QtQuick framebuffer readback. Subsequent
  format, session and large-cloud runs completed without these errors.
- Potree classification visibility setters create unknown class entries
  without a color. Clear Filters exposed this defect. The application supplies
  a complete fallback style before invoking the existing Potree setter.
- Closed/failed viewers disable camera and Save Session controls.
- Session restoration is acknowledged only after matching renderer telemetry,
  not immediately when restoration commands are queued.

Attempt folders retain `viewer_run.json`, `stdout.log`, `stderr.log`,
`prepare_stdout.log` and `prepare_stderr.log`, including failed launches.
Records distinguish parent/child Qt versions, observed stages, exit status,
exceptions, WebEngine errors and requested shutdown origin. WebEngine process
termination is connected using the documented
[Qt WebEngine signal](https://doc.qt.io/qt-6/qml-qtwebengine-webengineview.html#renderProcessTerminated-signal).
Missing final evidence remains unknown, not an invented clean shutdown.

## Local Format and Session Evidence

QGIS 3.44.13 / Qt5 and QGIS 4.0.0 / Qt6 each passed LAS, LAZ and COPC
deterministic renderer tests with 20,000-point fixtures:

- Fit, orbit, pan, zoom, Top and Front.
- Classification and elevation color changes.
- Source-Z filter and Clear Filters, with canvas PNG evidence.
- Hidden child launch and clean shutdown, exit 0.

These actions use the actual Potree control implementation through value-only
IPC. They are not substitutes for final human mouse/keyboard acceptance.

Save/reopen after page destruction passed on both QGIS versions, preserving
camera position/orientation/radius, Elevation mode, class 5 visibility, and Z
range 2-6. Existing Phase 34A1 session/journal contracts are reused. Changed
source fingerprints reject replay and offer explicit recovery choices.

Fixture source hashes before/after matched:

- LAS: `b18bdb4c66e3fb186977ce77e9eb7e6514a3da8fccd6bd9019c3347ca991250f`.
- LAZ: `4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866`.

Class controls show only codes encountered in resident streamed nodes. The
list is explicitly called Observed classes, not a full-source inventory.
Discovery inspects at most 50,000 resident classifications per telemetry tick
and does not request additional source data. Show/hide, solo and Show All
support values 0-255; no scientific attributes or journal entries are changed.
Unseen classes retain prior visibility. HAG filtering is not yet qualified.

## Failure Isolation and Layout

Both Qt5 and Qt6 passed deliberate termination of the harness-owned renderer
process tree. The UI reported disconnection and disabled unusable controls.
Process and Tools & Setup navigation remained available; scientific engine
status was READY before and after. Reload rendered again and final shutdown
exited 0.

Widths 420, 600, 760, 1100 and 1400 passed control-boundary checks with filters
expanded. Viewer heights were 276 px in Qt5 and 262 px in Qt6 for that expanded
900 px dock harness. Filters are collapsed by default; the normal viewer gets
the remaining space. QWidget captures document controls; separate canvas
captures document the cross-process viewer.

The existing Mission Control smoke again passed 100 construction cycles,
100 navigation cycles, four engine states, and no new scientific imports.

## Olaa: Real 104.8M-Point Qualification

User-selected source:
`X:\PROJECTS_2\Bugs_from_Space\OJ_temp\OlaaFR_RoadSite_PC_CHM\OlaaFR_RoadSite_Heli_Thin05_CropPC_Norm.las`.

- LAS 1.4, 104,819,538 points, 3,773,503,743 bytes.
- XYZ bounds preserved: X 271368.874-272118.751; Y 2152762.757-2153464.879;
  Z -7.078-23.643.
- Source SHA256 before and after:
  `dda1c1bab4da2a6c41cb620bc2fc1f256f4920714ac30bcde826aa963208fc67`.

The existing QGIS-bundled Untwine executable was invoked as an explicit
qualification tool, not installed or made a production viewer dependency.
[Untwine](https://github.com/hobuinc/untwine) produced a separate COPC under
test artifacts, never beside or over the source. The harness enforced a
6 GiB monitored-memory ceiling and 1,200-second conversion deadline.

- Source fingerprint: 77.813 seconds.
- Index build: 133.203 seconds, exit 0.
- Maximum monitored indexer memory: 1,148,764,160 bytes.
- Output COPC: 1,425,693,643 bytes; all 104,819,538 points preserved.
- Total including both source hashes: 283.657 seconds.

| Actual COPC viewer run | Qt5 | Qt6 |
| --- | --- | --- |
| Ten interaction/filter steps | PASS | PASS |
| First useful reported view | 5.688 s | 5.984 s |
| Total harness duration | 44.344 s | 41.234 s |
| Peak sampled process-tree private memory | 684,032,000 B | 675,299,328 B |
| Peak sampled summed working sets | 773,136,384 B | 764,973,056 B |
| Final displayed points, before filtering | 215,880 | 215,880 |
| Source bytes served | 4,385,319 | 4,385,319 |
| Source range requests | 9 | 9 |
| Final exit code | 0 | 0 |

Frame intervals were approximately 16.7 ms. This is renderer animation-frame
timing, not an independently measured GPU benchmark. Working sets may include
shared pages; sampled private bytes are reported separately. First-view timing
uses positive displayed-point telemetry; nonblank first-frame PNG is recorded
separately in the attempt log.

Actual adaptive refinement was observed: roughly 77,254 displayed points at
the initial view, rising to 215,880 as the camera settled. Budget was reduced
during motion and increased afterward. Source traffic was bounded byte-range
streaming, not a full cloud read. Large source GETs without a bounded Range
are refused; HEAD remains available.

**Boundary:** automatic large unindexed LAS preparation is not yet integrated
into normal viewer setup. The normal 2M-point guard remains. This evidence
proves the derived indexed source is interactive, not a completed one-click
large-LAS workflow.

## Installed Package and Protected Process

The experimental ZIP was extracted into a new, isolated QGIS profile under
test artifacts. Real QGIS 3.44 loaded the plugin from that profile, registered
it, opened Mission Control and rendered LAZ in the embedded Point Cloud page.
Default user profiles/projects and QGIS installations were not modified.

Desktop automation could inspect the complete rendered page and accessibility
tree, but refused viewport drag input because the child surface belongs to
the isolated Python renderer, not the target QGIS process. One documented
activation/refresh retry produced the same ownership error. No bypass was
attempted. This is an automation limitation, not a viewer crash. The user then
explicitly confirmed that mouse orbit, pan and wheel zoom work normally.
Those three interactions are human-confirmed; remaining actions retain their
separately identified deterministic-harness evidence.

The unchanged backend execution API completed a real CHM canary from the tiny
LAZ: success, no warnings/errors, 1 m grid, embedded EPSG:32605, using existing
classified-ground Delaunay preparation. An earlier canary explicitly supplied
EPSG:32610; the subsequent source-CRS canary corrected that test input and also
passed. This confirms real scientific runtime
execution, not a mocked result. A complete installed-UI Prerun workflow still
needs dedicated evidence.

## Evidence Locations and Harnesses

Windows evidence root:
`C:\Users\Milo\Documents\PyForestScan-QGIS\artifacts\phase34a2`.
Subfolders include `format-acceptance`, `qt5-session-ack`,
`qt6-observed-classes`, `qt5-failure`, `qt6-failure`,
`olaa-index-qualification`, `qt5-olaa-large`, `qt6-olaa-large`,
`process-canary`, `installed-qt5`, and `experimental-package`.

Managed attempt records/screenshots:
`C:\Users\Milo\AppData\Local\PyForestScan\backend\viewer\runs\<run_id>`.
Harness result JSON records each exact attempt folder.

Promoted harnesses in `scripts/testing/`:

- `qgis_point_cloud_viewer_smoke.py`: renderer commands and memory/traffic evidence.
- `qgis_point_cloud_session_smoke.py`: page recreation and session restoration.
- `qgis_point_cloud_failure_smoke.py`: owned-child failure/reload and width checks.
- `qualify_untwine_view_cache.py`: explicit out-of-core index qualification.
- `windows_viewer_memory.py`: read-only process-tree memory sampling.

Scratch/prototype files outside the repository remain preserved pending final
promotion or explicit rejection. No prototype/runtime directory is packaged.

## Validation and Remaining Gates

Full suite final recheck: 1,068 tests passed with 7 skips, including the new
transport regression. The original 81 protected
regressions passed. Compile, repository undefined-name check, help coverage,
package validation and packaged import graph passed. Help reported no missing
used topics or generic placeholders; 37 orphan registered topics were reported.

Normal release packaging correctly refused the dirty worktree. An explicitly
dirty developer package was built outside `dist`. Release validation passed
after supplying the correctly named versioned ZIP and identical latest alias.
That checks artifact consistency; it does not certify interactive beta readiness.

Still required before full Phase 34A2 completion:

- Installed-QGIS Qt6 evidence (Qt6 standalone page harnesses already pass).
- Authoritative polygon selection, full-resolution regional resolution,
  highlighting and selection statistics; no editing of LOD samples.
- Actual EPT streaming qualification and safe EPT session/tree identity.
- Managed automatic large-LAS indexing, cache repair and dependency lifecycle.
- HAG-only-when-present filtering and complete source metadata in sessions.
- Full installed Process Prerun/Recent Results workflow evidence. The real
  existing batch preflight API passed with no blockers/warnings and detected
  embedded EPSG:32605; the CHM runtime canary passed separately.
- Final lifecycle/orphan checks, final packaging and coherent milestone commit.

No version bump, commit, push, tag or GitHub release has occurred.
