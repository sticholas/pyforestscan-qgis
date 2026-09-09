# Linked Point Cloud Workspace Architecture

Status: **LINKED_VIEW_ARCHITECTURE_EXPERIMENTAL** (Phase 34A3.4).

This is not a claim that Area Detail or Vertical Slice is available. The running
interface currently exposes only **3D Overview**. New source-space geometry,
workspace subscriptions, metadata roundtrip and resource allocation contracts
are implemented and tested; derived-view rendering/query adapters are gated.

## Exactly one authority

| Domain | Owner | What a view may do |
| --- | --- | --- |
| Original source / fingerprint | SourceIdentity and managed editor session | Reference, never rewrite |
| View cache | Managed cache/indexer | Read for visualization, never use cache order as point identity |
| Session / selection definitions | PointCloudEditSession and SelectionDefinition | Submit intent through the controller |
| Resolved membership / count | Managed SelectionResolver | Display the canonical result |
| Staged edits / undo / redo | One session journal in editor_worker | Issue global commands, never create per-view journals |
| Export | Existing export materializer | Request a new derivative, never replace the original |
| View metadata | PointCloudWorkspaceModel registry | Own camera, ROI, render mode and local display filters |

The Qt workspace model is a control-plane facade. Its editor snapshot is a
detached copy of worker-authored metadata, not another source of edit authority.
Subscribers receive the same selection ID, full-resolution count and overlay
reference. A view may show only the portion present in its resident LOD; that
does not change selected membership or the global count. Sample indices are not
accepted as original point identities.

A session change resets old view geometry and selection metadata even when the
new session references the same source file. Stale revisions are rejected within
a session. One failing observer does not block other subscribers.

## Geometry and interaction contracts

View identities are OVERVIEW_3D, AREA_DETAIL and VERTICAL_SLICE. The main renderer
is explicitly 3D Overview. The tab container exists, but does not advertise
unimplemented creation actions or instantiate several renderers at startup.

AreaGeometry supports rectangle, square, circle and polygon metadata with source
CRS and explicitly source-unit dimensions. Editing geometry does not change
source or session identity. These metadata validators are not a substitute for
backend topology validation before execution.

SliceGeometry persists endpoints A/B, thickness, CRS, Z or HeightAboveGround,
and optional vertical limits. Local coordinates are distance along A-to-B,
selected vertical ordinate, and signed perpendicular distance. Missing HAG is an
error, never silently replaced by Z. Units are not assumed to be metres.

### Requested selection intersection

The following is the execution contract for the next implementation, not a
working profile query today:

1. Restrict depth to the corridor around A-to-B, with half the thickness on each
   side and finite endpoint limits.
2. Intersect with a profile-space selection polygon or an explicitly selected
   above/below/between-height interval.
3. Optionally intersect with a separate top-down footprint polygon.
4. Apply explicitly enabled global data filters.
5. Resolve against the immutable original source and distribute ONE result.

Thus a top-down polygon and a side polygon select their intersection, not their
union and not two unrelated render samples. All views show the same source-point
selection, clipped visually by their own display filters and LOD.

Current Polygon/Rectangle selection remains an XY column through source Z.
It temporarily uses a top view to avoid interpreting angled screen coordinates
as a false source footprint. Completion/cancellation restores the prior camera.
Arbitrary angled 3D selection requires a validated frustum/depth-volume adapter;
removing the top-view conversion alone is scientifically incorrect.

## Global versus local filters

ViewState.display_filters is local visualization state. Changing it does not
mutate the workspace global_filters or another view. The existing single-view
selection behavior is preserved: its current class/Z filters are included in
the source selection. A future multi-view controller must offer an explicit
global-selection-filter choice rather than copy arbitrary active-tab display
filters into all selections.

## Resource and persistence foundation

ViewerResourceCoordinator assigns the total point allowance only to the active
view and zero to inactive views, bounded by an explicit RAM accounting allowance.
High measured frame time reduces that allowance. This is a tested allocation
policy, NOT yet a measured multi-renderer GPU allocator.

Registry metadata roundtrips with source-fingerprint checks, including active
view, geometry, cameras, local filters and render mode. It creates no renderer
during restore. This API is not yet wired to persistent multi-tab session UI;
the existing single-view session save/reopen remains in use.

Next implementation must enforce those allocations in live renderer lifecycles,
suspend inactive rendering, retain lightweight state, release GPU buffers safely,
and reactivate only the selected tab. No arbitrary maximum view count is imposed.

## Remaining execution gates

- Area Detail creation toolbar, direct dimension controls, spatial renderer query,
  editing adapter and Show in Overview navigation.
- Slice endpoint gesture, thickness/height controls, 2D profile renderer,
  full-resolution corridor/profile intersection and background cancellation.
- Indexed cache-to-original identity strategy for bounded queries on massive raw
  LAZ. Repeated full-source scans are not acceptable for interactive slicing.
- EPT immutable affected-node identity and edit/export qualification. EPT remains
  view-only; repository metadata hash alone is insufficient.
- Live shared overlay/selection/undo propagation across real derived views.
- Persistent tab restoration and actual global GPU/RAM budget enforcement.
- LAS/LAZ/COPC/EPT benchmark matrix and human linked-view acceptance.

No sub-two-second latency claim, linked-view beta claim, or Phase 34A5 progression
is authorized by the current foundation.
