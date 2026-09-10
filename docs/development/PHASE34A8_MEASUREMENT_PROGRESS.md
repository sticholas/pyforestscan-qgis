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

## IN PROGRESS

Point-to-point and planar-area measurements have contract, renderer, worker and
dual-Qt test coverage. Human point picking/drawing, label readability,
dense-source latency and detached-view visual agreement still require live
qualification.

## NEXT

1. Qualify point picking and linked overlays in a fresh human viewer session.
2. Add profile/cross-section measurement records using authoritative source
   coordinates.
3. Add linked-location markers and lightweight annotations to the existing
   workspace model.

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

Measurement overlays store segment vertices relative to the first endpoint and
place the Three.js object at the source-coordinate origin. This retains
sub-metre Float32 geometry precision for large projected coordinates.
