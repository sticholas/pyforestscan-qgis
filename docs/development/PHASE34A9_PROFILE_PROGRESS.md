# Phase 34A9 Profile Workbench Progress

State: **IN PROGRESS**. This is an incremental extension of the established
Vertical Slice workflow, not completion of the professional profile milestone.

## Current Slice

The active Vertical Slice now presents a compact Profile toolbar with direct
Fit, Reverse Profile and corridor Width controls. Its summary names the axes,
shows the corridor width and reports the exact number of original source points
inside the bounded corridor. A tooltip includes profile length, display-sample
count and the source-resolved LAS classification distribution.

Overview and Area Detail now also provide **Profile: Multi-segment Path**. The
user draws two or more source-XY vertices and finishes with double-click,
Enter, right-click, or the first vertex. The resulting Vertical Slice flattens
the path to cumulative distance along profile, signed cross-track distance,
and elevation or HAG. Reverse Profile reverses the complete path rather than
only exchanging the original endpoints.

The bounded query accumulates classification counts before display sampling.
Consequently the profile summary does not mistake rendered LOD points for edit
authority. Reverse and Width update the existing linked-view definition, retain
the single shared selection/edit journal, and rerun the bounded query. Original
LiDAR remains unchanged.

Profile corridor footprints are now broadcast from the same linked-workspace
registry to Overview and Area Detail renderers. They are display-only source
coordinate outlines, can be hidden per view under Scene overlays, and never
carry point identities, selections or edit authority. The active profile uses
a distinct line tone without relying on color as its only identity; renderer
telemetry records the number of accepted profile overlays.

Multi-segment queries use one bounded source envelope per segment for indexed
LAS/LAZ and an exact corridor polygon for COPC/EPT readers. The display cache
retains original XYZ in reserved provenance dimensions while its display XYZ
uses the flattened profile coordinates. Selection, above/below-line editing,
measurements, and annotations project through the shared path geometry and
resolve against original source records. Display samples never become edit
authority.

Pointer hover now publishes a transient, source-bound linked cursor. Hovering a
flattened profile uses the cache's reserved original XYZ provenance to report
source coordinates, distance along path, cross-track distance, elevation or
HAG, and classification. The same source record is projected into every open
Overview, Area Detail, and Profile renderer as a subtle linked marker. Ordinary
Overview/Detail hover is truthfully labeled as a displayed source-record
coordinate; profile provenance is labeled as original-source coordinate data.
Cursor state is intentionally neither persisted nor admitted to selection or
edit authority. Picking temporarily exposes CPU provenance to Potree and removes
the temporary GPU attributes immediately afterward.

Architecture decision: **REUSE** PDAL reader polygon clipping plus the
established linked-workspace and scene-visibility state; **ADAPT** the raw-source
range index to per-segment envelopes; **WRAP** flattened display caches with
original-XYZ provenance; **IMPLEMENT** one shared cumulative-distance projection
and exact corridor-membership contract. No second source, selection, journal,
or workspace authority was introduced.

## Qualification Boundary

QGIS-free contracts cover path validation, cumulative projection, corridor
membership, per-segment source queries, authoritative selection, measurements,
annotations, and renderer gesture completion. Existing linked-view tests cover
the shared workspace and journal boundaries.

Remembered profile camera, profile-specific point-size
and color quick actions, and sustained human editing acceptance remain
unfinished. Two-point Vertical Slice remains available alongside the new path
profile.

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
85 tests under both QGIS 3.44.13/Qt5 and QGIS 4.0.0/Qt6. The production Node
renderer harness also verifies one footprint object, its source-space placement,
display-only authority marker, telemetry count and visibility toggle. This is one real-source
query measurement, not sustained profile interaction or human acceptance.

A second real-source canary used a two-segment path against the same
2,287,408-point LAZ. It scanned 380,928 indexed candidates, resolved 81,151
authoritative corridor points, and prepared the flattened display result in
1.344 seconds. Cumulative display distance ranged from 0.002 to 424.979 source
units, cross-track distance stayed within the approximately 20-unit corridor,
and the maximum independent projection difference was below 0.00000005 source
units. The source SHA256 was unchanged. This is measured extraction and
coordinate evidence, not a sustained-interaction qualification.
