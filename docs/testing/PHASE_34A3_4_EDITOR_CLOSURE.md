# Phase 34A3.4 Editor Closure and Linked Workspace Evidence

Release state: **LINKED_VIEW_ARCHITECTURE_EXPERIMENTAL**.
No public release, version bump or default-QGIS-profile replacement.

## Human findings and closure

The user reported that Rectangle/reclassification worked, Polygon could not
finish, right-click escaped, and the help footer resized the viewer. They also
reported intermittent-looking RGB behavior and requested linked detail/slice
views with shared source-point selection and spacious viewing areas.

After the isolated corrected-build test, the user confirmed: "yes all of this
works". This records PASS for the requested Polygon completion, help stability,
RGB explanation and Rectangle/classification retest. It is not a claim of human
acceptance for export, derived views or camera restoration added afterwards.

Current completion gestures: double-click, Enter, right-click or click the first
vertex. Escape cancels. Invalid, self-intersecting or extremely small boundaries
produce a terminal error rather than a half-finished tool. Rectangle retains its
drag interaction. Resolver failure restores the prior authoritative overlay.
A subsequent change restores the pre-selection camera on completion/cancellation;
production event-handler tests cover it, human confirmation remains separate.

## Executed checks

| Check | Actual result |
| --- | --- |
| Pure drawing / RGB capability matrix | PASS |
| Production editor pointer/keyboard event handlers | PASS; not selection_test shortcut |
| Complete Qt5 page, 1,000 help changes | PASS, 48-pixel help height; canvas invariant |
| Complete Qt6 page, 1,000 help changes | PASS, 48-pixel help height; canvas invariant |
| Real small-LAZ renderer canary | PASS, 124 telemetry samples, no renderer errors |
| User Polygon/help/RGB/Rectangle retest | PASS as reported above |
| Real QGIS editor regression | PASS, all ten steps |
| Source selection / export equivalence | 814 selected/reclassified; 20,000 output points; original SHA unchanged |
| Session reopen / owned renderer crash / reload | PASS in the ten-step canary |
| Process handoff | PASS; no scientific job automatically started |
| Workspace subscriptions and source/session isolation | QGIS-free contract tests; no live derived views |
| Area Detail / Slice human acceptance | NOT RUN; execution adapters not implemented |

Small-LAZ RGB diagnosis used ORIGINAL_RGB values before decoder normalization:
731,534 observed records, min/max Red=0, Green=0, Blue=0. The message explicitly
says sampled values are zero, not that every source in every view has broken RGB.
A previous full-source audit of this same LAZ also found zero colors.

RGB states distinguish valid, low-range, all-zero, constant, partial, missing and
renderer failure. Raw LAS/LAZ/COPC decoded nodes carry bounded metadata statistics;
binary EPT may expose only decoded-color diagnostics and is labelled accordingly.
The pinned decoder uses identity scaling for effective 8-bit nodes, or division
by 256 for values above 255, equally for all channels. No source value changes,
per-channel stretching or invented colors. Mixed-encoding nodes require further
cross-node qualification; this is not a whole-repository normalization audit.

Raw evidence lives under the local Windows workspace:
artifacts/phase34a3_4/editor-fix-canary,
artifacts/phase34a3_4/human-editor-closure and
artifacts/phase34a3_4/protected-editor-canary.

Protected export SHA256:
4522d60e0a6ec1fc7eb04c7dc59994851b5e5e75d2b68c0c5012d04655b73ab4.
Original tiny LAZ SHA256:
4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866.

## Prior soak result is retained, not rewritten as PASS

The earlier 34A3.3 60-minute Olaa run completed 14,351 samples and 601 mixed
transitions but FAILED its geometry gate with 74 flags. Final render remained
499,875 points at about 60 FPS. Private memory rose from 397,484,032 to
1,221,484,544 bytes, peak 1,225,043,968 bytes. These numbers alone do not prove
leak freedom or classify every layout event.

That run preceded this phase's help/footer fixes. It also toggled selection
controls which legitimately changed layout. The full mixed soak needs a
state-aware rerun; the old failure remains evidence, not an all-green stability
claim. A two-hour soak and weak-hardware qualification have not been executed.

## Scope boundary

See [linked workspace architecture](../development/POINT_CLOUD_LINKED_VIEWS.md).
The Overview tab is usable. Area Detail/Slice geometry, registry, synchronization
and resource policy are foundational contracts only. There are no actionable
fake tabs, no derived renderer benchmark results and no live EPT editing claim.
All-view selection must represent the same original points, not independent LOD
samples. Depth, height and intersecting top/side polygons are recorded contracts
for the next implementation.
