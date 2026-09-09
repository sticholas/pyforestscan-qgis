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
This evidence does not qualify interactive circle drawing or export on every
format, nor does it establish massive-source selection latency.

## IN PROGRESS

Circle/cylinder backend membership is available to the existing resolver but
is not yet exposed as a finished user-facing tool. Radius remains explicitly
in source XY units; no screen-pixel or implicit metre conversion is allowed.
Circle plus HAG range is a height-relative column, not a Euclidean 3D cylinder.

## NEXT

1. Direct circle drawing/preview and explicit radius/depth controls using the
   existing tool and background selection dispatch.
2. Sphere/volume and brush contracts with authoritative depth semantics.
3. Real linked-view editing/export checks and human interaction acceptance.

## BLOCKED

No access blocker. Do not promote to editor beta until the inherited linked-view
gates and professional selection acceptance are actually satisfied.
