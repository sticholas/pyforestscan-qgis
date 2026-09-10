# Phase 34A9 Profile Workbench Progress

State: **IN PROGRESS**. This is an incremental extension of the established
Vertical Slice workflow, not completion of the professional profile milestone.

## Current Slice

The active Vertical Slice now presents a compact Profile toolbar with direct
Fit, Reverse Profile and corridor Width controls. Its summary names the axes,
shows the corridor width and reports the exact number of original source points
inside the bounded corridor. A tooltip includes profile length, display-sample
count and the source-resolved LAS classification distribution.

The bounded query accumulates classification counts before display sampling.
Consequently the profile summary does not mistake rendered LOD points for edit
authority. Reverse and Width update the existing linked-view definition, retain
the single shared selection/edit journal, and rerun the bounded query. Original
LiDAR remains unchanged.

## Qualification Boundary

QGIS-free contracts cover axis wording, authoritative counts, class summaries,
loading state and invalid geometry. Existing linked-view tests cover the shared
workspace and journal boundaries. Live Qt layout, real-source query latency and
human interaction still require qualification before this slice is accepted.

Multi-segment profile paths, linked cursor/readouts, remembered profile camera,
and profile-specific point-size/color controls remain unfinished. Polygon,
rectangle, above-line and below-line edits continue to use the already
source-resolved two-point Vertical Slice path.

## Measured Evidence

A bounded HAG profile query ran against the 2,287,408-point Windows LAZ fixture
using the installed managed runtime. The 140 by 20 source-unit corridor scanned
141,312 index candidates and resolved 28,916 original points in 0.765 seconds.
Its exact class totals were Ground 16,800; High vegetation 9,909; Low vegetation
2,030; Unclassified 150; and Medium vegetation 27. The query display retained
all 28,916 corridor points under its 250,000-point budget.

The original SHA256 remained
`0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb`.
Focused QGIS-free tests pass, and the linked-view/controller suite passes all
60 tests under both QGIS 3.44.13/Qt5 and QGIS 4.0.0/Qt6. This is one real-source
query measurement, not sustained profile interaction or human acceptance.
