# Polygon LiDAR Stabilization

Phase 27R surgically restores a reliable ordinary-folder polygon workflow without rolling the repository back to Phase 27L or Phase 27M.

The restored beta path is:

1. Select an ordinary folder containing LAS, LAZ, or COPC files.
2. Select a Polygon or MultiPolygon from QGIS, disk, or WKT.
3. Inspect/read source headers into one shared `LidarSourceMetadata` model.
4. Establish an explicit effective CRS from embedded metadata or a repository CRS override.
5. Select all real source paths whose bounds intersect the full polygon envelope.
6. Preserve the exact Polygon/MultiPolygon geometry for clipping and raster masking.
7. Pass only selected source paths into PBM clipping requests.
8. Run products from clipped sources.
9. Mask final rasters to the exact polygon.
10. Register final outputs for Results and QGIS loading.

## Historical Audit

| Behavior | 27L | 27M | Current before 27R | Decision |
|---|---|---|---|---|
| Folder discovery | Catalog-first polygon Batch; ordinary folders required a built catalog. | Same, plus shared batch options. | Phase 27Q added direct header fallback. | Keep direct metadata as the correctness path; catalog is optional optimization. |
| Source bounds | Header/catalog bounds drove envelope selection. | Same. | Catalog and direct paths could use different representations. | Add shared `LidarSourceMetadata` for direct and catalog-derived metadata. |
| CRS handling | Catalog CRS and EPT CRS diagnostics existed; unknown ordinary CRS blocked. | Same. | Phase 27P added explicit repository CRS overrides. | Keep explicit assignment; apply overrides to missing-CRS metadata without editing source files. |
| File selection | Selected catalog paths were handed into polygon clipping. | Same. | Direct fallback selected paths, but no centralized invariant. | Add selected-path invariants and manifest/debug selected path serialization. |
| Polygon transport | Phase 27L introduced durable polygon input validation for PBM. | Retained. | Retained. | Keep durable polygon transport unchanged. |
| PBM execution | Logical EPT/COPC and ordinary clipped-source handoff existed. | Retained. | Retained, but all-COPC logical detection was too broad. | Keep EPT native; ordinary folders, including multiple COPC files, use selected file paths. |
| Masking | Request validation existed. | Phase 27M added exact raster masking. | Retained. | Keep exact masking and failure policy. |
| Output registry | Basic batch summaries. | Shared generated-output registry for polygon results. | Retained. | Keep registry and final masked output registration. |
| QGIS loading | Results loading came through shared generated outputs. | Retained. | Retained. | Keep duplicate-safe Results loading. |

The divergence was not one bad scientific algorithm. The brittle point was the selection contract: after the catalog system became central, ordinary-folder processing could look prepared while selected execution paths were absent, stale, or catalog-only. Phase 27Q restored a direct selector; Phase 27R makes that selector the stable ordinary-folder contract and protects the path into execution.

## Stable Core

`LidarSourceMetadata` is now the shared source metadata record for ordinary folders. It records:

- real path and canonical path;
- source type;
- existence and readability;
- size and modification timestamp;
- bounds and point count;
- embedded CRS, repository override, and effective CRS;
- metadata reader and signature;
- status and errors.

`HeaderMetadataService` reads headers without loading full point arrays. The current QGIS-free implementation uses the existing catalog header reader/fallback code path. PBM-backed metadata can be added later behind the same model.

`DirectLidarFolderSelector` consumes `LidarSourceMetadata`, applies the full polygon envelope, and returns real selected paths. The exact polygon geometry is not simplified for final clipping or masking.

`PolygonLidarProcessingService` creates a support/debug plan that makes selected paths the execution contract. Polygon Batch preflight and execution also enforce the ordinary-folder invariant:

```text
selected_sources > 0
implies
selected_source_paths has the same count and every path is readable
```

## Ordinary Folders Versus EPT

Ordinary LAS/LAZ/COPC folders:

- discover real files;
- read file headers;
- apply explicit effective CRS;
- select files by envelope overlap;
- clip exact polygon through PBM;
- run products from clipped files.

EPT:

- resolve one logical `ept.json` source;
- derive request bounds from the polygon envelope;
- pass exact polygon geometry to PBM;
- keep EPT internal node files out of Batch selection.

Multiple COPC files are treated as ordinary file-level candidates. A single future native COPC path may use native spatial access only when repository identity explicitly says it is a logical source.

## Current Limits

The automated suite verifies the selected-path contract, durable polygon handoff, exact masking integration, and output registry behavior with QGIS-free fakes. Live QGIS validation is still required before claiming a specific Windows/QGIS repository passed. Use [Real Ordinary LiDAR Polygon Validation](../testing/REAL_ORDINARY_LIDAR_POLYGON_VALIDATION.md).

## Phase 27S EPT Alignment

Native EPT source selection now resolves the EPT CRS before comparing extents. Malformed CRS metadata produces a CRS-specific blocker, not a false no-coverage result. When CRS values match semantically, preflight takes a fast path; when they differ and a QGIS or PBM transformer is available, the exact polygon geometry is transformed before the broad EPT envelope is derived.
