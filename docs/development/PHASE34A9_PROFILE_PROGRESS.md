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
edit authority. Potree returns hidden CPU-only node/index metadata after its
ordinary pick, allowing the editor to read provenance without changing the
registered GPU attribute layout.

The shared display row now names its rendering selector **Color By** and remains
directly available in Profile. Color mode, circular/square point style, point
size, quality, filters, and camera remain per-view workspace state. Restoration
now waits for renderer acknowledgement of point style and size as well as camera,
color mode, filters, and quality; the top-level non-destructive edit session also
retains those appearance choices. This reuses the existing workspace authority
instead of introducing duplicate profile controls or state.

Brush Select now operates directly in the Profile plane. The renderer transmits
only a simplified distance-along-profile plus elevation/HAG stroke and radius;
the managed worker queries the bounded source corridor, projects original source
records into that plane, and applies exact round-capped membership. Replace,
Add, and Subtract therefore use the same authoritative selection sequence and
journal as every other view. Display samples remain only interaction guidance.

Architecture decision: **REUSE** PDAL reader polygon clipping plus the
established linked-workspace and scene-visibility state; **ADAPT** the raw-source
range index to per-segment envelopes; **WRAP** flattened display caches with
original-XYZ provenance; **IMPLEMENT** one shared cumulative-distance projection
and exact corridor-membership contract. No second source, selection, journal,
or workspace authority was introduced.

## Qualification Boundary

QGIS-free contracts cover path validation, cumulative projection, corridor
membership, per-segment source queries, authoritative polygon/rectangle/brush
selection, measurements, annotations, and renderer gesture completion. Existing
linked-view tests cover the shared workspace and journal boundaries.

Sustained human profile editing acceptance remains unfinished. Two-point
Vertical Slice remains available alongside the new path profile.

The repeatable real-source qualification entry point is
<code>scripts/testing/pbm_point_cloud_profile_brush_smoke.py</code>. It compares
the production resolver with an independent full-source round-stroke
calculation and verifies that the source fingerprint is unchanged. The
independent comparison is deliberately limited to sources with at most three
million points; massive-source production queries remain corridor-bounded.

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

The managed Profile Brush canary used a 291.421-source-unit, two-segment HAG
profile with a 20-unit corridor and a horizontal round stroke covering HAG
0-10. The production resolver and an independent original-record calculation
both selected exactly 49,084 points with identical class totals: 231
Unclassified, 19,321 Ground, 4,225 Low vegetation, 49 Medium vegetation, and
25,258 High vegetation. Resolution and comparison completed in 0.640 seconds.
The canary intentionally scanned all 2,287,408 fixture points to provide an
independent reference; indexed production display/selection remains bounded by
the source corridor. The source SHA256 remained
<code>0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb</code>.

A QGIS 3.44.13 human session then exposed an unsafe first implementation:
hover had added provenance attributes after Potree created the geometry's GPU
buffers, and Potree dereferenced a missing buffer version. The corrected path
leaves geometry attributes untouched and fails a transient cursor read closed.
The follow-up small-LAZ session ran for 1,095.39 seconds with no renderer
errors, reached 1,003,046 displayed points at full-cloud scale, created one
multi-segment profile, and repeatedly resolved profile selections. The final
selection contained 327 original records from 589,824 candidates in 3.719
seconds; source buffers remained unchanged.

Human review confirmed Profile Brush interaction works, while identifying
unfinished usability gates: Replace/Add/Subtract semantics are not adequately
explained; elevation/HAG range filtering can make a selection appear to vanish;
profile axes and units are not visible enough; view and measurement selectors
are overcrowded; and classification actions need stronger staged-edit
confirmation. These are accepted Phase 34A9 UX work, not qualified behavior.

## Selection And Measurement UX Slice

The editor now presents the existing selection combination contract as **Start
new selection**, **Add to selection**, and **Remove from selection** beneath an
explicit **New shape** label. The worker protocol continues to receive
`REPLACE`, `ADD`, and `SUBTRACT`; no second selection state was introduced.

The selection-height row now names its scope, active view, axis, low/high
interval, and the fact that it applies to the next shape. Choosing Elevation
initializes from the source's actual Z bounds rather than the previous invented
0-50 interval. A **1-unit band** action sets High exactly one source-height unit
above Low, so a user can combine a thin vertical interval with Rectangle,
Circle, Brush, Polygon, Box, or Profile geometry. HAG remains available only
when the immutable source exposes a stored `HeightAboveGround` dimension. A
zero-result replacement now explains that no authoritative points matched the
active height interval instead of presenting an unexplained empty highlight.

Profile renders now include visible X and Y axes. X reports distance along the
profile; Y reports elevation or stored HAG. Projected source CRS units are
derived through QGIS where possible and source-local data is explicitly labeled
as source units. Axis setup runs both when the linked-view context arrives and
when the point cloud finishes loading, so command ordering cannot suppress it.

View options are grouped by linked view, scene overlay, view creation, current
view, comparison, and saved viewpoint. Measurement actions are grouped into
3D distance, profile cross-section distance, tree height, planar area, and
linked-marker annotation. Classification now uses **Class presets**, **Stage
Classification**, **Auto-stage new selections**, and **Point flags** wording.
Explicit classification staging confirms the authoritative point count, target
class, undoability, derivative-only behavior, and source immutability before it
enters the shared journal.

The focused controller suite passes 66 tests under QGIS 3.44.13/Qt5 and 66 under
QGIS 4.0.0/Qt6. QGIS-free presentation and renderer-contract tests pass, as does
the production JavaScript gesture harness. Human layout and interaction review
of these controls remains required. More realistic forest rendering, improved
depth cues, and appearance presets remain a separate unfinished slice; this UX
change does not claim those visual-quality gates.
