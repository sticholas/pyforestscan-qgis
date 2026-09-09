# Phase 34A4: Linked-view acceptance

Release state: **LINKED_VIEWS_EXPERIMENTAL**. Human acceptance has not passed.
Base: `30a9011`. This report records incremental work, not a release claim.

## Human baseline

The user tested the isolated QGIS 3.44.13 editor on
`D:\LiDAR_Temp\215000_2114500_g_h_c_h_unbuf_hag.laz`.
Selection agreed across views. Tab switching and opening Area Detail were
too slow, with temporarily empty views. Dragging tabs out did not work.
Menus, selection depth, padding terminology and square point rendering were
confusing. These failures override earlier automated canary success.

The former field defaulting to 2 is traced to `LinkedViews.from_selection`:
`QInputDialog.getDouble` returns floating-point padding in source XY units.
Each side is expanded by that amount: width/height = bounds span + 2 * padding.
It affects the detail region, not point size, spacing, resolution or edit depth.
It now reads "Extra margin on each side (dataset XY units)" and defaults to
zero. A regression verifies that zero preserves the selected XY span and an
explicit margin of two adds four to each dimension, without changing point
display size. Specific CRS unit-name presentation remains pending; do not
assume metres for a source with unknown coordinates or geographic units.

## Done

- Shared immutable selection definitions support area clipping, corridor
  thickness, profile polygons, elevation/HAG limits and explicit filter opt-in.
- Bounded display extraction uses the original source or its validated display
  cache; edits still resolve original records through one editor/journal.
- A three-view warm renderer pool now retains native surfaces and cameras.
  Inactive windows are hidden, not restarted on ordinary return switches.
  Older retained renderers are stopped on capacity eviction. Geometry changes
  invalidate the corresponding resident renderer; source changes/unload drain
  parked workers. Hidden-window CPU/GPU pressure still needs soak measurement.
- Reactivation suppresses replay of the last selection gesture and resends the
  shared edit overlay. Surface signals target their own worker.

## Measured evidence

Evidence directory on the test machine:
`C:\Users\Milo\Documents\PyForestScan-QGIS\artifacts\phase34a4`.

| Run | Result | Evidence |
| --- | --- | --- |
| human-linked-01 | Failed human usability acceptance | User report above; automated JSON alone does not encode that report |
| resident-hag-01 | Passed automated 15-step canary | Same Overview/Slice workers retained; undo/redo, session, export and handoff |
| resident-hag-02 | Passed automated 22-step canary | Fresh snapshot replies after switching, native screenshots, detached edit/redock and export |
| detach-action-01 | Passed automated 22-step canary | Direct accessible Detach icon, shared 467-point profile selection, redock, three-edit export; 75.08 s total |
| surface-transfer-01 | Passed automated 22-step canary | Same renderer through detach/redock; attachment acknowledged before retiring native container; nonblank captures |
| surface-transfer-20 | Passed on QGIS 3.44.13 | Twenty repeated detach/redock cycles plus final shared edit/export; same renderer retained |
| surface-transfer-qgis4-01 | Passed on QGIS 4.0.0 | Three repeated transfers plus final shared edit/export; original SHA256 unchanged |
| direct-tools-01 | Passed on QGIS 3.44.13 | Rectangle/Polygon buttons in main and detached views; three transfer cycles, shared edits and export; 69.30 s |
| inline-hag-limits-01 | Passed on QGIS 3.44.13 | Inline HAG 8-18 controls and source-bound checks; test reapplied limits after reload |
| inline-hag-limits-02 | Passed on QGIS 3.44.13 | HAG 8-18 automatically restored from workspace; linked selection, transfers, undo/redo, export; 69.69 s |

For resident-hag-02, both warm returns completed by the next 250 ms test
poll. This is a polling upper bound, not a precision frame-latency benchmark.
Native `warm-overview.png` and `warm-slice.png` were inspected and nonblank.
First creation still took approximately 11 s for Area Detail and 9 s for Slice.
Detach and redock still recreate the renderer and each took about 10 s.

The source contains 2,287,408 points. Authoritative area selection resolved
1,676 points; profile selection resolved 467. Export after three operations
preserved the count, all unedited dimensions, CRS and custom VLR payloads.
The original source SHA256 remained:
`0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb`.
Detached export SHA256:
`fd4e62b2323c48de0ff402f4f34fb4f37fd75c6e0dbd2386be314abec168f66b`.

Focused validation: 137 point-cloud tests passed with 7 optional-runtime skips,
including 6 new resident lifecycle tests. Undefined-name checking and Node
gesture/decoder lifecycle tests passed. The real QGIS canary covers scientific
selection/export unavailable in the skipped WSL tests.

## In progress / next

Selection limits are now an inline control beside the editor tools in both
main and detached views, not a hidden depth dialog. Choices are Full column,
Elevation range (original Z), and Height above ground (stored HAG, when present).
Slice defaults explicitly say Within slice thickness and show its width.
Minimum/maximum fields are inclusive; changing limits affects the next
selection, not existing selections or staged operations. Display filters remain
opt-in. The controls share the existing workspace global-filter store and
save/reopen with that workspace; no second selection state or journal exists.
Source changes clear next-selection limits without writing that reset into the
previous session. Saved height values are validated before restoration.

Invalid ranges disable drawing and explain the error; missing HAG is not
silently presented as Full column. Disjoint view/filter intersections are
reported before selection dispatch. Numeric typing is protected from telemetry
refreshes. Height labels deliberately say stored height units rather than
assuming metres. The first UI capture exposed a clipped HAG label; the combo
now sizes to its current contents and has a width regression assertion.

The persistent-limits canary resolved 623 area points (HAG 8.02-16.48) and
246 slice points (HAG 8.06-16.48) from the original 2,287,408-point source.
Three-edit export preserved all non-edited values, CRS, custom VLRs and source
SHA256. Export SHA256:
`e1049d97387b6b4935845244cc347f718e72214c1b8dbf7f407e6e7e1af2e78b`.
Focused tests: 162 run, 22 optional-runtime skips, no failures. Actual Qt
control/event tests: 15 pass on each installed Qt generation. These are
automated checks; human acceptance and full milestone validation remain open.

Pointer/Navigate, Polygon Select and Rectangle Select now use a shared compact
exclusive icon strip in main and detached views. There is no hidden tool combo.
Area Detail and Vertical Slice have direct QGIS-theme icon buttons. View
options retains less frequent polygon-region and adjustment actions. Tool
icons have semantic help, accessible names and stable 28-pixel logical sizing.
Nine actual Qt widget/event tests pass on each installed QGIS version,
including the zero-margin regression. The focused tier runs 150 tests with
16 QGIS/native-dependency skips; no failures. Compilation, undefined-name
and documentation-link checks pass.
The direct-tools canary clicks the selection controls before resolving geometry;
creation-button wiring is checked separately, not claimed as a human drawing
test. Source-safe export SHA256 still matches the earlier result.
The UI-only capture was reviewed for layout; its blank foreign-renderer area
is not evidence of failed rendering (native-host captures are used for that).
The current selection tool still temporarily uses top view for 3D XY drawing,
as stated in its tooltip; preserving arbitrary 3D selection projection is not
implemented by this control-only change.

Drag-out now detects boundary crossing during mouse movement and ends Qt's
tab-reorder grab before dispatching the window change on the next event turn.
A direct Detach View icon is available beside Linked views, with semantic
tooltip and accessible name. Four actual Qt event tests pass under both
installed QGIS 3.44/Qt5 and QGIS 4.0/Qt6 (cross-boundary single dispatch, click,
reorder and release fallback). This does not replace the failed human drag
acceptance; real mouse retesting remains required.

Native surface transfer now keeps the same renderer, source/cache lease and
camera. The old container remains alive until the host acknowledges its new
parent. Commands retry for up to ten seconds; a timeout stops only that viewer
before retiring its container, leaving source/edit authority untouched.
Focused tests cover acknowledgments, retries, timeout cleanup and ownership.
The first real test retained the renderer through both moves and redocked
within one 250 ms poll. Its nine-second detach test wait also included opening
the main Overview after session reload; it is not a pure transfer latency.
Subsequent canaries record host acknowledgment timing separately.

Across surface-transfer-20, detach acknowledgment was 15-63 ms (44.1 ms mean)
and dock acknowledgment 16-78 ms (19.85 ms mean). These are command/host
acknowledgment measurements, not human-visible frame latency. Final detachment
and docking were each observed by the next 250 ms poll. Native captures
after moving and returning were nonblank. The final three-edit export SHA256
matched the earlier `fd4e62...8f66b` result on QGIS 3.44 and QGIS 4.
This validates the tested Windows machines/runtimes only, not Linux/macOS.

Current focused validation: 145 point-cloud tests passed with 11 skipped in
the QGIS-free tier; four Qt event tests ran separately on each installed QGIS
version. Ten resident/transfer tests include failure cleanup. Compilation,
undefined names and help-topic coverage checks passed (37 orphan registered
help topics remain; no missing used topics or generic placeholders reported).

1. Reliable drag-out and visible Detach/Dock access, preferably moving retained
   surfaces rather than restarting the view.
2. Direct spatial tools, explicit selection limits, semantic units and circular
   point rendering with simple sizing controls.
3. Faster first creation, session/window restoration, resource-pressure and
   large-source qualification.

## Point appearance slice

Main and detached views now expose Circular/Square point sprites and an
Automatic or 1-16 screen-pixel size control in the existing display row.
Automatic retains the adaptive 2-5 pixel policy. These settings affect display
only, not density, selection depth, source attributes, or exports. Appearance
is view-local and restored with the linked editing workspace.

The isolated QGIS 3.44 point-appearance-01 canary passed in 95.55 seconds on
the 2,287,408-point small LAZ. Sixteen combinations of shape, size (Automatic
and 8 px), and Classification/Elevation/RGB/Intensity passed renderer material
checks. Native screenshots show nonblank circular points and shared selection
in the HAG profile. Frame-time samples were approximately 16.66-16.67 ms;
these short, vsync-limited samples are not a sustained performance benchmark.
This source has all-zero RGB, reported explicitly rather than treated as
usable color. A second tiny fixture passed all sixteen appearance combinations
with constant RGB; varied RGB on a large source remains a qualification gate.

HAG-limited area/profile selection, shared edits, reopen, detach/dock, and
validated export passed. Appearance persisted across reopen and native surface
transfer. Detach/dock host acknowledgments were 62/15 ms in this run; initial
view creation still takes seconds and is not represented by those timings.
The original source was unchanged, all 2,287,408 points were retained, and the
three-edit export SHA256 remained
e1049d97387b6b4935845244cc347f718e72214c1b8dbf7f407e6e7e1af2e78b.

Validation: 167 focused tests ran with 24 dependency skips, 17 Qt control tests
passed on each installed QGIS 3.44 and QGIS 4.0 runtime, and JavaScript render
policy, compilation, undefined-name, and documentation-link checks passed.
Human interaction retesting, read-only EPT session appearance persistence,
large-source rendering, resource stress, and sustained soak remain open.

## Blocked gates / package status

No access blocker currently prevents development. Release gates remain open:
human retest, large LAS/LAZ/COPC/EPT linked-view coverage, 21-view/100-cycle
stress coverage, 100 alternating edits, 60-minute soak and milestone validation.
No new package, tag, public release or default-profile deployment is claimed.
