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
Sphere membership and transport are implemented but deliberately have no user
gesture yet. A renderer sample, camera depth, or guessed vertical center cannot
become sphere authority.
Box Select is exposed with explicit depth semantics and automated contract and
real-source evidence. Human drawing acceptance and a full QGIS export canary
remain open.

## NEXT

1. Human circle/cylinder interaction acceptance in Overview and Area Detail,
   including Add/Subtract and the active height limits.
2. Human Brush acceptance plus cancellation qualification on the 104.8-million
   point source or another representative massive local cloud.
3. Complete human Box drawing acceptance and its full linked-view/export
   canary, then design an explicit sphere placement gesture without camera-depth
   or rendered-point authority.

## BLOCKED

No source/test-data access blocker. Do not promote to editor beta until the
inherited linked-view gates and professional selection acceptance are actually
satisfied.
The current full Box canary is temporarily blocked by all configured viewer
runtime slots being retained by an older live QGIS session. No user process was
terminated; rerun after those viewer windows or that QGIS session close.
