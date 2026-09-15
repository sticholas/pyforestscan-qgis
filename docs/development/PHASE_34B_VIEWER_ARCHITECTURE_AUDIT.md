# Phase 34B Viewer Architecture Audit

## Scope

This audit records the architecture at the start of Phase 34B. It is a
working engineering boundary, not a claim that the viewer is release-qualified.
The viewer remains an experimental `0.2.0-beta.1` capability and QGIS manual
qualification is still required.

## Authoritative State

- `PointCloudWorkspaceModel` owns view identity, active view, view geometry,
  camera, display filters, LOD preferences, bookmarks, and persisted view state.
- `EditorPanel` and the point-cloud editor worker own the authoritative source
  selection snapshot, edit journal state, staged attributes, measurements,
  annotations, and source fingerprint.
- Selection membership is resolved against original source records. Rendered LOD
  points are display evidence only and are never valid scientific addresses.
- `SelectionProcessingScope` is the single serialized bridge from the editor to
  scientific product planning. It carries source identity, source-space closed
  geometry, scope kind, source-point count, CRS, and optional Z/HAG limits.
- The managed Processing Engine/PBM boundary owns scientific execution. QGIS
  Python remains a fallback/runtime boundary and External Worker mode remains
  disabled.

## Presentation-Only State

- Potree/WebGL rendered samples, adaptive budgets, refinement labels, point
  sprites, color ramps, and display filters are presentation state.
- View telemetry may report a changing sample count while a view refines. The
  `DisplayTelemetryStabilizer` only smooths labels; it does not alter rendering
  or source queries.
- View-specific cameras differ by view, but selection, edit, cursor, and source
  identity remain shared.

## Runtime Flow

1. `PointCloudPage` owns the QGIS widget, isolated viewer worker, surface, and
   top-level display controls.
2. `LinkedViews` coordinates Overview, Area Detail, and Vertical Slice views. It
   manages active-view transitions, query-worker requests, detached windows,
   cursor synchronization, and resident renderers.
3. `linked_query_worker.py` performs bounded source queries and produces cached
   display artifacts. Request IDs and cache keys reject stale results.
4. `ResidentViews` parks acknowledged renderers and transfers native surfaces
   without stopping the worker. Capacity is bounded to protect graphics memory.
5. `DetachedView` can own a transferred renderer while the page editor remains
   the shared selection/edit authority.
6. The editor sends selection commands to the active renderer, but the worker
   resolves geometry against original source data and publishes an authoritative
   snapshot back to the workspace.
7. Product requests are created as review artifacts, pass an explicit product
   preflight, and are promoted into derived plans without modifying the base
   Product Plan or source file.

## Source-Space vs Display-Space

| Concern | Display-space | Source-space / authoritative |
| --- | --- | --- |
| Point count | Rendered sample / budget | Resolved source selection count |
| Selection | Gesture pixels and visible nodes | Original XYZ records and geometry |
| Profile | Rendered profile surface | Bounded corridor query |
| Measurement | Cursor preview | Source coordinates and source units |
| Color | GPU display attribute | Source dimension availability and filters |
| Product processing | Never uses arbitrary LOD points | PBM bounded source read |
| Edits | Overlay / staged preview | Edit journal keyed to source fingerprint |

## Asynchronous Boundaries

Safe to run asynchronously:

- source preparation and indexing
- bounded display queries
- renderer subprocess communication
- source-authoritative selection resolution
- measurements and profile analytics
- PBM scientific processing
- cache validation and source fingerprinting

Must remain on the QGIS/UI thread:

- Qt widget creation and destruction
- native viewer surface ownership/reparenting
- QGIS layer/project operations
- signal/slot-driven UI state updates

Every asynchronous result must be associated with a request, source identity,
view identity, or edit revision before it can update shared state.

## Expensive Operations

The principal expensive operations are full-resolution source scans, raw LAS/LAZ
index creation, profile corridor queries, source fingerprinting, PBM preparation,
and analytics over large scopes. These must not run synchronously during camera
interaction. Cached display artifacts are reusable only when source fingerprint,
geometry, view type, and cache identity match.

## Known Duplication / Debt

- View telemetry, editor snapshots, and workspace view state overlap in several
  transitions and require explicit acknowledgement rules.
- Product availability was previously derived separately by UI guidance and the
  preflight gate; Phase 34B now introduces one shared capability registry.
- The viewer has a compact display control row but does not yet have a full
  reusable layout model for split analytical panes.
- Profile axes and cursor context exist, but dynamic legends, analytics scopes,
  and measurement quality metadata are not yet unified models.
- Source fingerprint revalidation now occurs before backend request construction
  for scoped jobs; an asynchronous UI-side promotion status is still a follow-up
  so hashing never blocks QGIS.

## Non-Negotiable Invariants

1. Rendered LOD points are never scientific truth.
2. The original source remains immutable.
3. There is one authoritative selection and one edit journal.
4. Stale asynchronous results cannot overwrite active state.
5. Heavy source work does not block QGIS interaction.
6. Managed PBM execution remains separate from QGIS Python.
7. Product availability labels must match actual scoped gates.
8. Measurements must state their source and quality limitations honestly.

## Phase 34B Implementation Order

1. Shared capability and source-integrity foundations.
2. Visualization model, legends, ranges, and dynamic scale infrastructure.
3. Editable profile refinements and bounded analytics.
4. Unified measurements and quality metadata.
5. DBH-assisted measurement foundation.
6. Plan/slicing layout and lifecycle performance.
7. QGIS manual qualification and release decision.
