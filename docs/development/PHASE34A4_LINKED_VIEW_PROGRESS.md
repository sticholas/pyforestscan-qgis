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

The field defaulting to 2 is traced to `LinkedViews.from_selection`:
`QInputDialog.getDouble` returns floating-point padding in source XY units.
Each side is expanded by that amount: width/height = bounds span + 2 * padding.
It affects the detail region, not point size, spacing, resolution or edit depth.
Renaming and unit-aware presentation remain pending; do not assume metres
for a source with unknown coordinates or geographic units.

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

1. Reliable drag-out and visible Detach/Dock access, preferably moving retained
   surfaces rather than restarting the view.
2. Direct spatial tools, explicit selection limits, semantic units and circular
   point rendering with simple sizing controls.
3. Faster first creation, session/window restoration, resource-pressure and
   large-source qualification.

## Blocked gates / package status

No access blocker currently prevents development. Release gates remain open:
human retest, large LAS/LAZ/COPC/EPT linked-view coverage, 21-view/100-cycle
stress coverage, 100 alternating edits, 60-minute soak and milestone validation.
No new package, tag, public release or default-profile deployment is claimed.
