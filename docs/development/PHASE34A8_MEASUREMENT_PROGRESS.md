# Phase 34A8 Measurements and Scene Tools Progress

State: IN PROGRESS. Measurements remain part of the experimental Point Cloud
Editor and do not change the `0.2.0-beta.1` release boundary.

## DONE

- Added a compact Point-to-Point measurement action that keeps the current 3D
  camera instead of forcing top view. Navigation is suspended only while two
  visible source points are chosen; Escape returns to normal navigation.
- Renderer picks are proposals, not measurement authority. The managed editor
  resolves both XYZ values to original source records in one bounded,
  cancellable full-source scan and rejects picks outside a conservative
  floating-coordinate tolerance.
- Saved measurements report 3D distance, horizontal distance, absolute vertical
  distance and signed elevation difference. CRS and horizontal/vertical unit
  labels are explicit. Geographic angular coordinates fail closed rather than
  being mixed with elevation; unknown CRS uses clearly labeled source units.
- Measurements are source-fingerprinted session metadata, not point edits.
  They survive autosave/recovery, have bounded count and duplicate guards, and
  never enter the edit journal or alter exports.
- Resolved lines and endpoint markers are broadcast to active, parked and
  detached linked renderers. Detailed values stay under Editing Details so the
  viewer retains its compact working area.
- The measure control now offers Planar Area without adding another toolbar
  button. It reuses the accepted source-coordinate Polygon gesture, validates
  the simple closed ring in the managed worker, and reports projected area and
  perimeter with explicit units. Large projected coordinates are translated
  before area calculation to avoid cancellation error.
- View options now supports named saved viewpoints. Each bookmark retains an
  exact validated camera and its Overview, Area Detail or Vertical Slice
  identity inside the existing source-bound linked workspace. Opening a
  bookmark activates that view and camera; closing a linked view removes its
  dependent bookmarks, and changing source/session clears them.
- Vertical Slice now has a distinct Cross-section measurement path. Elevation
  slices resolve renderer XYZ against original source XYZ; HAG slices resolve
  display height against the stored `HeightAboveGround` dimension while
  retaining original XYZ. Results report along-profile distance, signed
  vertical change and cross-section distance. They are shown only in their
  owning slice so HAG display coordinates cannot be confused with elevation.
- Added source-bound linked markers with bounded names and optional notes. A
  renderer click remains only a proposal: the managed worker re-resolves it
  against the immutable full-resolution source, retains source XYZ,
  classification and HAG when present, and persists the marker in the existing
  editing session without creating a point edit.
- Linked markers render in Overview and only in Area Detail or Vertical Slice
  views whose geometry contains the resolved source point. HAG slices use the
  stored HAG value for display while retaining original elevation as marker
  authority. Active, parked, newly opened and detached renderers receive the
  same marker state. Add, inspect, rename, edit note, remove and clear actions
  remain under compact Measure and Editing Details menus.
- Area Detail and Vertical Slice views can now be given validated, unique names
  from the existing View options menu. Names remain part of the sole
  source-bound linked-workspace record, survive session recovery, and update
  existing tabs and detached-window titles without recreating renderers.
- View options now contains a compact dynamic Linked Views switcher. It lists
  every named view with its type, identifies separately-windowed views, opens
  tabbed views through the existing lazy renderer lifecycle, and raises detached
  windows directly. It introduces no second scene registry and reserves no
  permanent viewer space.
- The Measure menu now includes a guided Tree Height action for Vertical Slice.
  The user picks a base and top while the same managed profile resolver resolves
  both against original records. Results report absolute tree height,
  horizontal offset and whether the vertical basis is elevation or stored HAG.
  HAG bases outside a one-unit ground tolerance and all elevation-based heights
  receive explicit interpretation guidance; zero-height picks fail closed.

## IN PROGRESS

Point-to-point, planar-area, cross-section, tree-height and linked-marker tools have contract,
renderer, worker and dual-Qt test coverage. Human point picking/drawing, marker
readability, dense-source latency and detached-view visual agreement still
require live qualification.

## NEXT

1. Qualify point picking, markers and linked overlays in a fresh human viewer
   session.
2. Qualify named-view switching and detached-window raising in a live session.
3. Design source-isolated multiple-cloud comparison views without merging edit
   journals or source fingerprints.

## BLOCKED

Human interaction acceptance requires an available embedded-viewer session.
Automated gesture and camera assertions do not replace mouse acceptance.

## MEASURED EVIDENCE

Managed Windows qualification used
`D:/LiDAR_Temp/215000_2114500_g_h_c_h_unbuf_hag.laz` through the installed PBM
Python. The resolver traversed all 2,287,408 original points in 0.469 seconds.
Both requested anchors resolved to exact source records with zero snap distance.
The result reported EPSG:6635 metre units, 69.305 metres horizontal distance,
3.130 metres elevation change and 69.375 metres 3D distance. The source SHA256
remained `0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb`
before and after the scan.

The same managed canary validated a 10 by 10 metre boundary at projected
coordinates near 215,000 / 2,114,500. It reported exactly 100 square metres and
a 40 metre perimeter, retained EPSG:6635 unit context, and left the same source
hash unchanged.

The managed canary also resolved a real HAG cross-section through all 2,287,408
source records in 0.454 seconds. Its two display anchors snapped exactly to
stored source points, retained original elevations 908.65 and 944.71 metres,
and used HAG values 0.00 and 18.850 metres for the profile. It reported 111.763
metres along the transect, +18.850 metres HAG change and 113.341 metres
cross-section distance. The source hash remained unchanged.

Those same exact source anchors produced a guided tree-height result of 18.850
metres with a 111.763 metre horizontal offset and an explicit HAG basis. The
base anchor was classification 2 at HAG 0.0, so no questionable-base warning
was required. This result reused the authoritative profile resolution evidence;
it did not interpret rendered samples as source truth.

Measurement overlays store segment vertices relative to the first endpoint and
place the Three.js object at the source-coordinate origin. This retains
sub-metre Float32 geometry precision for large projected coordinates.

The linked-marker canary resolved source coordinate
`215000.000, 2114534.320, 908.650` through all 2,287,408 original records in
0.469 seconds. It matched the exact source point at zero snap distance, retained
classification 2 and HAG 0.0, and left the source SHA256 unchanged. Renderer
tests place that same source anchor at original Z in Overview, filter it out of
unrelated Area Detail views, and place it at stored HAG in a matching HAG slice.
