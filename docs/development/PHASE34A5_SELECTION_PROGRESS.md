# Phase 34A5: Professional Selection Tools

State: IN PROGRESS. Linked views remain LINKED_VIEWS_EXPERIMENTAL.
The updated user objective is recorded in the attached goal-objective.md
(attachment 6caabca4-ffa0-4903-8f26-dcb16d451ade). Existing Phase 34A4
human interaction, long-run/resource, and source-format gates remain open.

## DONE

- Added optional exact source-XY circle center/radius to SelectionDefinition.
- Existing reader/index envelopes conservatively bound the circle; membership
  uses the analytic radius, not a tessellated polygon or display sample.
- Existing Z/HAG ranges create height-limited circular columns. Classification,
  attributes, linked-area clipping, slice constraints, Replace/Add/Subtract,
  source identity, and original-attribute journal replay remain shared.
- Serialization carries circle intent into replay. A mismatched envelope,
  incomplete circle, invalid radius, and unrepresentable extent fail closed.
- No new dependency, scientific algorithm, or second editing authority.
- Circle Select is a direct compact action beside Polygon and Rectangle in
  docked and detached tool strips. Drag center-to-edge to define the source-XY
  radius. Shift/Alt continue to mean Add/Subtract. The existing Full column,
  Elevation, or HAG selector supplies depth semantics.
- Renderer events carry exact center/radius through the UI and worker into the
  same SelectionDefinition and journal. Renderer selection/edit overlays retain
  those fields, so a circular authoritative selection is not shown as its
  rectangular query envelope.
- Circle use in Vertical Slice currently fails clearly and returns to Navigate;
  profile-circle semantics are not silently approximated.
- Added one authoritative round-capped Brush corridor primitive. A brush is a
  path of 1-512 distinct source-XY points plus a positive radius in dataset
  units. It is one SelectionDefinition, not hundreds of tool-owned selection
  records. Existing Replace/Add/Subtract, Z/HAG/class filters, source identity,
  journal replay, and conservative COPC query bounds remain authoritative.
- Brush membership uses exact point-to-segment distance with round endpoints.
  The renderer receives the same path/radius fields used by source resolution,
  so future brush overlays need not treat screen pixels or an envelope as edit
  authority. Circle and brush primitives are mutually exclusive.
- Brush Select is now a direct compact action in docked and detached tool
  strips. A contextual radius control appears only while Brush is active and
  stores one shared dataset-XY value in the linked workspace. Dragging samples
  a bounded source-space path and submits one authoritative corridor selection;
  the existing depth control supplies Full column, Elevation, or HAG limits.
- Brush previews use round caps/joins and source-scale width. Invalid radius,
  degenerate paths, paths over 512 samples, and Vertical Slice use fail closed.
  The renderer event, managed worker, selection resolver, journal, overlays,
  session restoration, export, and Process handoff retain the same path/radius.
- Linked-tab drag-out now requires vertical movement outside the tab strip, so
  reordering wide tabs cannot accidentally detach a view.
- Added one optional exact sphere primitive to the same SelectionDefinition.
  Its center is source X/Y/Z or source X/Y/HeightAboveGround, its radius is in
  the corresponding source units, and its depth mode is explicitly
  SPHERE_VOLUME. The XY circle is only a conservative indexed-query envelope;
  authoritative membership is the inclusive three-dimensional Euclidean test.
- Sphere fields survive serialization, renderer projection, docked/detached
  event transport, journal replay and export. Circle, Brush and Sphere remain
  mutually exclusive primitives. Missing stored HAG, invalid axis, incomplete
  center/radius, mismatched envelope, or implicit depth semantics fail closed.
  No Sphere button is exposed before a professional 3D placement gesture exists.
- Added one QGIS-free selection-impact policy shared by managed enforcement and
  docked/detached status text. Selections over one million points or 10 percent
  of the source receive a compact review cue. The existing stronger threshold
  (over ten million points or 25 percent) still requires explicit confirmation
  before staging an edit. Routine selections add no warning or permanent panel.
- Brush strokes longer than 512 captured samples now simplify only after every
  sample is converted to source XY. Short paths remain exact. Long paths use an
  iterative Ramer-Douglas-Peucker pass with maximum permitted deviation capped
  at one quarter of Brush radius; paths that still exceed 512 vertices fail
  clearly rather than being silently distorted. The exact simplified path and
  tolerance are preserved in selection/session/journal/overlay/export metadata.
- Selection progress now reports original-source candidate records examined,
  rather than only matched records, so a narrow Brush does not appear stalled
  while valid chunks contain no matches. Cancellation is polled at every
  bounded reader chunk, selection operation, and Brush segment. The editor
  acknowledges one cancellation request, disables duplicate cancellation, and
  retains the prior authoritative selection and journal when interrupted.
- Added direct Box Select without adding a second volume engine. In Overview
  and Area Detail it requires explicit stored Elevation or HAG limits, then
  combines those with a dragged source-XY rectangle. In Vertical Slice, the
  profile rectangle and existing source-XY corridor thickness define the
  volume. Replace/Add/Subtract, linked-area clipping, source identity, resolver,
  journal, undo/redo and export remain the existing shared contracts. Missing
  vertical limits in a 3D view fail before the tool arms; camera depth is never
  inferred.
- Exposed the existing exact Sphere contract as a compact direct action with
  explicit placement. The linked workspace owns one persisted center-height
  axis (source Z or stored HAG) and value shared by docked and detached views;
  center-to-edge drag supplies source XY center and source-unit radius. The
  contextual controls are visible only while Sphere is active, preserve
  partially typed values during telemetry refresh, and remove HAG when the
  source lacks that dimension. Vertical Slice use fails clearly. The gesture
  emits the same sphere fields already used by the resolver, renderer overlay,
  journal replay and export; camera depth and rendered point identity remain
  irrelevant.
- Added direct Invert Selection in docked and detached editors. Inversion is an
  explicit replayed property of the current selection step, so later Add and
  Subtract operations retain deterministic boolean order. The resolver scans
  the complete original source for inverted LAS, LAZ and COPC selections rather
  than negating a query envelope or visible LOD. It remains cancellable in the
  managed background, reuses large-selection review/confirmation, and leaves
  the previous authoritative selection intact on failure or cancellation.
- Added compact Grow/Shrink Selection actions in docked and detached editors.
  The first production contract deliberately accepts one non-inverted Replace
  selection: Circle and Brush radii resize analytically, Sphere radius resizes
  in three dimensions, and polygon/Box XY outlines use a managed Shapely
  buffer. Existing Z/HAG limits do not change. Composite, inverted, split,
  removed, over-complex, and Vertical Slice results fail closed while retaining
  the previous authoritative selection. The managed worker resolves the new
  definition against original source points before it replaces editor state;
  journal, undo/redo, overlays and export therefore keep one authority.
- Added compact Select Above Line and Select Below Line actions that appear
  only in Vertical Slice. A two-point gesture is converted to exact
  `(distance along slice, Z or HAG)` endpoints before it leaves the renderer.
  Authoritative membership includes only the line segment's horizontal span,
  the full configured slice-corridor thickness, and points inclusively above
  or below its interpolated height. Existing class and height filters and
  Replace/Add/Subtract order continue through the shared SelectionDefinition,
  managed resolver, edit journal, overlay and export path. Reversed endpoints
  are equivalent; vertical, degenerate, outside-slice, non-slice and competing
  profile shapes fail closed. Screen pixels and rendered point identity are
  never retained as edit authority.

## MEASURED EVIDENCE

The installed Windows managed runtime resolved a circle at source XY
(215250, 2114750), radius 15, HAG 8-18 against
D:/LiDAR_Temp/215000_2114500_g_h_c_h_unbuf_hag.laz.
It scanned 2,287,408 original records and resolved 1,795, all class 5.
Observed resolver duration: 0.516 seconds (single run, not a benchmark).
Selected HAG: 8.010004997253418 through 16.480018615722656.
Original source SHA256 was verified unchanged:
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.

The new tests cover inclusive circle boundaries, bounding-box corner exclusion,
filters, Add/Subtract, source-query bounds without LOD options, invalid input,
serialization, and journal replay without original-array mutation.
Production JavaScript gesture tests cover center-to-edge drag, exact source
coordinates, circle preview shape, camera restoration, completion/cancellation,
and explicit Vertical Slice rejection.

The QGIS 3.44 linked canary on the same 2,287,408-point HAG source passed all
15 automated steps in 45.407 seconds. A radius-7.5 circle in Area Detail with
HAG 8-18 resolved 491 original points; its staged edit survived session
save/reopen and combined with a 246-point slice edit. The validated full-source
export preserved point count, every non-edited dimension, CRS, custom VLRs,
and source hash. Output SHA256:
546622d1f31995eff915b6f672474579c755fbea69ffc613146eb2da3a60bc6a.
The saved journal contains circle_center, circle_radius, linked-view identity,
and HAG constraints.

The QGIS 4.0 compatibility canary on the immutable 20,000-point tiny fixture
also passed all 15 steps in 40.078 seconds. Its validated export SHA256 is
643353aab23b092b40c52e2bbb2969b66c27f6a697c28fb41463adc0ab5baa7f;
source SHA256 remained
4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866.

These canaries inject the production renderer event protocol but do not
substitute for human center-to-edge drawing acceptance. They do not establish
massive-source selection latency or support Circle inside Vertical Slice.

A three-point Brush path from (215240, 2114740) to (215260, 2114740) to
(215260, 2114760), radius 2 and HAG 8-18, resolved 456 class-5 points from the
same 2,287,408-point LAZ in an observed 0.547 seconds. Source SHA256 remained
unchanged. Eight managed geometry tests cover rounded segment/end membership,
turns, envelope exclusion, height constraints, invalid paths, serialization,
worker overlay projection, and inherited filter/mode preservation. The combined
brush/circle/drawing set runs 26 tests without skips in managed Python.
This short-path observation is not evidence for 512-point strokes or massive
sources. Raw LAS/LAZ currently uses the existing bounded-chunk scan; interactive
stroke sampling/simplification and cancellation latency still need measurement.

Production JavaScript gesture tests now cover sampled freehand completion,
source-coordinate conversion, one exact path/radius event, invalid radius,
resolution state, and explicit Vertical Slice rejection. The direct controls
passed 25 focused tests in both QGIS 3.44.13/Qt5 and QGIS 4.0.0/Qt6 (one expected
Node-unavailable skip in each QGIS Python runtime).

The QGIS 3.44 real-LAZ linked canary passed all 15 stages in 54.937 seconds.
A three-segment Brush corridor in Area Detail with HAG 8-18 resolved 284
original class-5 points in 0.375 seconds, combined with a 246-point slice edit,
survived session reopen, and produced a validated 2,287,408-point LAZ. Every
non-edited dimension, CRS and custom VLR matched; the original SHA remained
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.
Output SHA256:
f78a8a2f59eb214dd40b974fdd492430545250baa3b59de37fb5e280554da32d.

The matching QGIS 4.0/Qt6 canary passed all 15 stages in 37.047 seconds on the
immutable 20,000-point fixture. Brush resolved 466 original points in 0.031
seconds; the two-edit export validated every dimension, CRS and VLR. Source
SHA256 remained
4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866;
output SHA256 is
e133d44d4a4c37234988a470be5c92e4de89442b86adf89ab563cf10520a4b0e.
These canaries exercise the production event protocol but do not replace human
freehand drawing acceptance or establish massive-cloud Brush latency.

A read-only managed-runtime sphere qualification used center
(215250, 2114750, HAG 10) and radius 5 on the 2,287,408-point HAG LAZ. The
production resolver selected 138 original class-5 records in 0.531 seconds,
exactly matching an independent predicate over every source record. Add without
double-counting and Subtract-to-empty passed. Source SHA256 remained
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.
Thirty-two managed geometry tests now pass across Circle, Brush and Sphere;
Sphere coverage includes source-Z boundaries, HAG membership, envelope-corner
exclusion, filters, modes, missing dimensions, serialization and journal replay.

The deterministic 2,048-sample Brush benchmark reduced a smooth source-space
path to 71 vertices. With radius 4, recorded tolerance was 0.1250008 source
units and independently observed maximum deviation was 0.1246027. Median
simplification time was 1.698 ms over 50 iterations on the test machine. An
adversarial 700-point zigzag exceeding the radius/4 deviation bound is rejected.
These are algorithm measurements, not dense-source selection-resolution times.

A managed-runtime cancellation qualification used a maximal 512-vertex Brush
against the immutable 2,287,408-point HAG LAZ. After the first 65,536 original
records were examined, cancellation was requested while resolution continued.
The worker acknowledged it in 0.406 seconds, raised `Selection cancelled; no
edits staged.`, and retained the source unchanged at SHA256
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.
Observed total resolver time was 0.797 seconds. This is one local-source
measurement, not a massive-cloud latency guarantee. The reusable qualification
is `scripts/testing/pbm_point_cloud_selection_cancel.py`.

A managed-runtime Box qualification used source XY bounds
(215240, 2114740)-(215260, 2114760) and stored HAG 8-18 on the same immutable
2,287,408-point LAZ. It resolved 1,139 original class-5 points in 0.500 seconds,
exactly matching an independent predicate over every source record. Add did not
double-count, Subtract returned empty, and source SHA256 remained
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.
The production drag contract and direct compact button pass QGIS 3.44/Qt5 and
QGIS 4.0/Qt6 focused tests. A full linked-view/export canary was attempted but
could not acquire a viewer host while an older live QGIS session retained all
three configured runtime slots; that user session was not interrupted.

The direct Sphere placement gesture passes the production JavaScript event
contract with center (1000, 2000, HAG 12) and radius 20, including camera
restoration. Its shared contextual controls and native icon pass focused tests
under QGIS 3.44/Qt5 and QGIS 4.0/Qt6. The earlier managed all-record sphere
qualification remains the authoritative membership evidence: 138 source points
at center (215250, 2114750, HAG 10), radius 5, with exact independent predicate
agreement and unchanged source SHA256. Human placement acceptance and the full
QGIS export canary remain open while viewer runtime slots are occupied.

An all-record Invert qualification negated the 1,139-point HAG-bounded Box on
the immutable 2,287,408-point LAZ. The resolver selected the exact complement,
2,286,269 points, in 0.500 seconds. Counts and classes matched an independent
NumPy predicate; ordinary and inverted partitions summed to the source header
count, and SHA256 remained unchanged. This proves local-LAZ semantics, not
large COPC performance; inverted COPC intentionally uses a complete source
reader and still requires massive-source qualification.

Grow/Shrink has managed geometry and dual-QGIS compatibility coverage. Its
real-source independent-predicate qualification is reusable as
`scripts/testing/pbm_point_cloud_selection_resize.py`; the measured result is
recorded after each immutable-source run rather than inferred from display LOD.

The managed-runtime qualification grew a source-XY Circle centered at
(215250, 2114750) from radius 5 to radius 7 dataset units while retaining HAG
8-18. On the immutable 2,287,408-point HAG LAZ, the original definition
resolved 189 class-5 points and the grown definition resolved 418 class-5
points. Both counts and classifications exactly matched independent predicates
over every source record. Combined resolution time was 1.062 seconds in this
single observation. Source SHA256 remained
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.
This establishes local-LAZ Circle growth correctness; it is not a massive COPC
latency result or human interaction acceptance.

A read-only Above Line qualification used a 20-unit source-XY Vertical Slice
centered across (215240, 2114750)-(215260, 2114750), corridor thickness 10,
and a stored-HAG line from profile distance 2 at HAG 8 to distance 18 at HAG
8. Against all 2,287,408 original records, the production resolver selected
527 class-5 points in 0.594 seconds. Count and classification distribution
exactly matched an independent profile-coordinate predicate. Source SHA256
remained
0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb.
The reusable qualification is
`scripts/testing/pbm_point_cloud_profile_line_smoke.py`. This establishes one
local-LAZ HAG membership case, not human line-drawing acceptance or massive
COPC latency.

## IN PROGRESS

Circle/cylinder selection is exposed but remains experimental pending human
interaction acceptance. Radius remains explicitly in source XY units; no
screen-pixel or implicit metre conversion is allowed.
Circle plus HAG range is a height-relative column, not a Euclidean 3D cylinder.
Brush is exposed and end-to-end automated evidence passes, but human freehand
acceptance and massive-source cancellation qualification remain required before
user release. Resolution already
runs in the managed background and large-selection impact feedback is now
shared with the edit-confirmation policy.
Sphere membership, transport and explicit placement are implemented. Human
placement acceptance remains required; a renderer sample, camera depth, or
guessed vertical center cannot become sphere authority.
Box Select is exposed with explicit depth semantics and automated contract and
real-source evidence. Human drawing acceptance and a full QGIS export canary
remain open.
Invert Selection is exposed with exact local-LAZ evidence. Large COPC latency,
human feedback and full export-canary coverage remain open.
Grow/Shrink Selection is exposed under its compact menu. Its single-Replace
contract is intentional; true morphology of arbitrary ordered Add/Subtract or
inverted composites is not approximated by resizing their component shapes.
Above/Below Line is exposed contextually in Vertical Slice with exact source
semantics and real-data evidence. Human drawing/edit/export acceptance remains
open.

## NEXT

1. Human circle/cylinder interaction acceptance in Overview and Area Detail,
   including Add/Subtract and the active height limits.
2. Human Brush acceptance plus cancellation qualification on the 104.8-million
   point source or another representative massive local cloud.
3. Complete human Box and Sphere drawing acceptance and their full linked-view/
   export canary after viewer runtime capacity is available.
4. Qualify Invert on a representative large COPC and confirm large-selection
   review/cancellation behavior in the live editor.
5. Complete human Grow/Shrink acceptance and a full export canary after viewer
   runtime capacity is available.
6. Complete human Above/Below Line acceptance with Z and HAG slices, including
   Replace/Add/Subtract and an exported classification edit.

## BLOCKED

No source/test-data access blocker. Do not promote to editor beta until the
inherited linked-view gates and professional selection acceptance are actually
satisfied.
The current full Box canary is temporarily blocked by all configured viewer
runtime slots being retained by an older live QGIS session. No user process was
terminated; rerun after those viewer windows or that QGIS session close.
