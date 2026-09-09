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

## IN PROGRESS

Circle/cylinder selection is exposed but remains experimental pending human
interaction acceptance. Radius remains explicitly in source XY units; no
screen-pixel or implicit metre conversion is allowed.
Circle plus HAG range is a height-relative column, not a Euclidean 3D cylinder.

## NEXT

1. Human circle/cylinder interaction acceptance in Overview and Area Detail,
   including Add/Subtract and the active height limits.
2. Sphere/volume and brush contracts with authoritative depth semantics.
3. Large-source circle resolution evidence and selection-impact feedback.

## BLOCKED

No access blocker. Do not promote to editor beta until the inherited linked-view
gates and professional selection acceptance are actually satisfied.
