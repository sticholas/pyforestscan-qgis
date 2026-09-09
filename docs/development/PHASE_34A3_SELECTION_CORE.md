# Phase 34A3 Selection Core and Qualification

Historical selection-only milestone, committed as f72a548. Current continuation
status and remaining editing gates are in the
[non-destructive editing record](PHASE_34A3_EDITING_LOOP.md).

Date: 2026-09-08. Starting commit: `0cc668ad972364a899886b7d0398ef272b98d582`.
Starting tree: clean `develop`. No reset, source edits, runtime installation,
QGIS profile modification, scientific behavior change or viewer architecture
replacement occurred.

Status: **EDITOR_EXPERIMENTAL**. This is an intermediate worker-only selection
core, not the completed 34A3 editing product. Package version remains 0.2.0-beta.1.

## Viewer Gates Rechecked

Existing 53 focused viewer/session tests passed before implementation.
The human-confirmed mouse orbit, pan and wheel zoom evidence is retained.

Fresh real-QGIS harness runs passed all ten camera/filter checks with clean
viewer exit 0:

- QGIS 3.44 / Qt5, tiny LAZ.
- QGIS 4.0 / Qt6, 104,819,538-point Olaa-derived COPC: first useful view
  6.937 seconds, sampled peak private process-tree memory 708,001,792 bytes.
- QGIS 3.44 / Qt5, real 110,008,858,527-point local/network EPT repository:
  first useful view 7.094 seconds; duration 30.328 seconds; 620,736,512 bytes
  sampled peak private memory; approximately 16.66 ms settled frame intervals.
  Final telemetry: 38,062 displayed points and budget 41,653.
  Transport: 2,622,216 bytes, 27 point-node requests, one hierarchy request,
  29 source requests total. No repository traversal or full-source download.
- The same EPT source passed the QGIS 4.0 / Qt6 ten-step harness.

EPT path:
`\\SDAVXTRA\X Drive\PROJECTS_2\Big_Island\ChangeHI_Trees\Dry_Forest\Data\Lidar\ept-full\ept.json`.

EPT root metadata SHA256 before/after:
`a84934f5ef6364db3406291f34e20e3c5b7cbec19545e5fb135a9478b5381a13`.
This proves unchanged root metadata, NOT the content identity of the entire
110-billion-point tree. Transport is read-only. No whole-tree hashing was done.

The previous LAS/LAZ/COPC Qt5/Qt6 evidence remains in
[34A2 acceptance](PHASE_34A2_INTERACTIVE_ACCEPTANCE.md).
No new human selection-tool acceptance is claimed.

## Source-Based Selection Contract

`core/point_cloud/selection.py` adds immutable SelectionDefinition and
SelectionResult contracts, plus a worker-only SelectionResolver.

- Closed source-XY polygon; finite coordinates; inclusive boundary rule.
  Polygon validity and membership use existing Shapely/GEOS, not a custom
  geometric implementation.
- Ordered Replace/Add/Subtract operates on original attributes. Add unions
  membership and cannot double-count; Subtract applies its own frozen filters.
- Source fingerprint, source type, session identity and CRS must agree across
  the selection sequence. Repeated selection IDs and LOD addressing are rejected.
- Z, HAG, original classification and numeric attribute filters are explicit.
  None means all classes; an empty class tuple means no classes.
- Known source CRS must match the request. Unknown CRS requires an explicit
  source-local identity bound to that file fingerprint; no invented EPSG code.
- COPC readers receive spatial bounds and two threads, with no resolution,
  depth or point-budget limit. Full-resolution candidate points are streamed
  in 65,536-point chunks with no prefetch.
- Separate positive selection regions use separate COPC queries, rather than
  reading a potentially enormous envelope between distant Add polygons.
  Overlapping query envelopes have deterministic first-query ownership;
  coincident original records are preserved, not deduplicated by coordinates.
- Exact polygon membership is evaluated after the envelope read. An envelope
  is not silently used as the selection.
- Small LAS/LAZ uses a bounded-memory sequential scan, limited to 2M points.
  Ordinary unindexed LAS does not gain random spatial access from a crop.
  Large unindexed selection remains disabled pending a verified spatial index.
- One resolver hashes the source on attachment, then checks file identity,
  size and timestamps before/after queries and between chunks. Reusing it
  avoids hashing a multi-GB file for every lasso. Reopen and eventual export
  must still verify content hashes independently. Same-stat hostile mutations
  are not cryptographically excluded by runtime stat checks.
- Statistics include source count, original class distribution, XYZ bounds,
  Z/HAG ranges, source partition path, candidate count and resolution timing.
  No selected-point array is retained across chunks.

The implementation follows [PDAL COPC reader bounds](https://pdal.org/en/stable/stages/readers.copc.html)
and [Shapely inclusive XY intersection](https://shapely.readthedocs.io/en/stable/reference/shapely.intersects_xy.html).

## Real Selection Evidence

Run `scripts/testing/pbm_point_cloud_selection_smoke.py` using the existing
managed scientific Python, never QGIS Python. The script writes only its
specified evidence directory.

| Source | Matched | Candidate points | Resolve time | Reference |
| --- | ---: | ---: | ---: | --- |
| 20k-point LAS | 3,006 | 20,000 | 0.016 s | Independent triangle inequality on original fixture |
| 20k-point LAZ | 3,006 | 20,000 | 0.016 s | Same independent predicate |
| 20k-point COPC fixture | 3,004 | 6,052 | 0.031 s | Independent predicate on that original COPC |
| 104.8M Olaa COPC | 20,405 | 38,872 | 0.391 s | Separate bounded full-resolution PDAL crop |

Times exclude fingerprint attachment, reference checks and final hashing.
They are local qualification measurements, not performance guarantees.
The pre-existing COPC fixture differs slightly from the LAS/LAZ at polygon
edges; each result is validated against its OWN source, not presumed cache
identity. Viewing caches must not become edit authority.

All sources passed Add-no-double-count, Subtract-to-empty and final SHA checks.
Olaa regional original classes: 17,810 class 1 and 2,595 class 2.

Source SHA256 values:
- LAS: `b18bdb4c66e3fb186977ce77e9eb7e6514a3da8fccd6bd9019c3347ca991250f`.
- LAZ: `4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866`.
- Tiny COPC: `f0cccb09b9d21a9f1fab2a7711814ffdc3f33cc92de84ce10bc1c427b16b8094`.
- Olaa COPC: `bea135c4eca2e3db0dd0079575f2e250b52cefd58c873af7f6edfc11086f3f37`.

Evidence root:
`C:\Users\Milo\Documents\PyForestScan-QGIS\artifacts\phase34a3`.
Subdirectories: `baseline-qt5-laz`, `baseline-qt6-olaa`,
`baseline-qt5-ept`, `baseline-qt6-ept`, `selection-las`,
`selection-laz`, `selection-copc`, `selection-olaa`.

## Remaining Implementation Gates

Validation at this checkpoint: 1,078 full-suite tests passed with 8 skips;
all ten new selection tests passed in managed Windows Python, including the
geometry test skipped in Linux. Compile, undefined-name, package and docs-link
checks passed. Existing help lint reported zero missing used topics and zero
generic placeholders (37 pre-existing orphan topics). QGIS 3.44 startup smoke
passed 100 construction and 100 navigation cycles with no new scientific imports.

No selection drawing buttons, staged edits, overlays, export action or version
bump are enabled by this core slice.

1. Integrate a managed selection subprocess with cancellation, timeout,
   progress, attempt diagnostics and generation-safe UI result delivery.
   Current resolver callbacks only cancel between PDAL chunks; a supervising
   process is necessary for a blocked native read.
2. Wire polygon/lasso/rectangle source-space geometry and preview distinction.
   Preserve accepted navigation and scope shortcuts to viewer focus.
3. Extend the existing session/journal schema rather than create another
   journal. Persist frozen membership semantics and replay original attributes.
4. Add classification/noise/withheld/removal operations and non-destructive
   overlay; preserve undo/redo across reopening and cache rebuild.
5. For EPT edit authority, verify affected hierarchy/node content or a durable
   immutable regional snapshot. Root metadata identity alone is insufficient.
6. Implement explicit new-file streamed materialization, dimension/CRS/VLR
   preservation validation, overwrite safeguards and failed-output cleanup.
7. Add Use in Process only for validated immutable exports.
8. Complete HAG display filtering, large-edit warnings, history benchmarks,
   UI/human acceptance, protected Process smoke and final release qualification.

Future brush/profile/segment interfaces must retain source partition identity;
rendered indices remain preview-only. Process Current Session stays design-only
until immutable snapshot materialization is proven.
