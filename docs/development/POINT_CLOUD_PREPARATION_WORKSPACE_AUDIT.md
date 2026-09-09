# Point-Cloud Preparation Workspace Audit

## Existing Contracts

- `core/advanced_processing.py:build_point_cloud_preprocess_request` validates
  Poisson radius, voxel cell/mode, optional HAG, and other filters.
- `core/adapter.py:preprocess_point_cloud` reads arrays, calls PyForestScan
  filters, and writes LAS/LAZ. It imports scientific modules directly; unlike
  routed products, this method has no PBM dispatch branch. Passing
  `execution_mode="pbm_backend"` at the algorithm call site does not itself
  route this method. Do not use that call directly inside the viewer UI.
- `core/lidar_preparation.py` and `core/lidar_preparation_execution.py`
  already own HAG planning, quality assessment, provenance, and checkpoint
  contracts. Reuse them rather than invent another ground/HAG algorithm.
- `core/point_cloud` owns authoritative selection, staged edits, and validated
  export. Any preparation based on staged edits must use that export, never
  the display query sample or a second edit journal.

## Managed Runtime Evidence

Artifact: `artifacts/phase34a4/preparation-functions-01/preparation-evidence.json`
in the Windows workspace. Command:

```text
<managed-python> -I scripts/testing/point_cloud_preparation_evidence.py --source <tiny.laz> --output-dir <new evidence directory>
```

PyForestScan version: 0.4.1. Installed filters source SHA256:
`f2b7ac0c6dd6ae8cfcd1b9edbf23049dabea194cb10dd7d25f50e2fb99e70c6f`.
This identifies the actual local runtime implementation, not an assumption
that every package with that version has identical source.

| Operation | Input points | Output points | Attribute evidence |
| --- | ---: | ---: | --- |
| Poisson radius 0.5 | 20,000 | 1,643 | Retained original records unchanged |
| Voxel cell 0.5, first | 20,000 | 3,931 | Retained original records unchanged |
| Delaunay HAG | 20,000 | 20,000 | Original dimensions unchanged; finite HAG added |

Distances are fixture coordinate units, not automatically metres.
AuditRecordId was attached to in-memory copies to verify original record
mapping; it was not written into the source. The source SHA256 remained
`4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866`.
This is a bounded filter test, not file publication, scientific accuracy
against ground truth, large-source scalability, or workspace acceptance.
The direct runtime invocation emitted a missing GDAL_DATA warning; use the
existing clean managed-process environment for the eventual workspace job.

## Integration Risks

1. The installed voxel filter accepts first/center only. Current advanced
   validation also lists last/nearest; those are not supported by this
   runtime. Keep Advanced Toolbox unchanged in this slice, but do not copy
   unsupported options into the workspace.
2. Voxel center changes XYZ to voxel centers. First retains real records and
   is the conservative choice for vegetation inspection and provenance.
3. Adding HeightAboveGround does not normalize Z. Replacing Z with HAG is a
   separate, explicit derived-dataset operation and must retain original Z
   provenance. A view height filter is neither operation.
4. Preprocessing loads arrays. It cannot be advertised as bounded-memory
   massive-cloud preparation without measured limits or an established
   compatible streaming/tiled execution path.
5. Existing preprocessing writes its requested output directly. The
   workspace needs owned staging, no-overwrite checks, validation, atomic
   publication, cancellation cleanup, and a source/output provenance record.

## Implementation Sequence

1. Add a preparation contract for immutable local sources or validated staged
   exports, explicit operations/units, new output paths, and resource checks.
   Reject EPT metadata as edit authority and never silently ignore staged edits.
2. Execute through the verified managed runtime with its clean subprocess
   environment. Reuse supported PyForestScan filters and HAG planner/quality
   checks. Preserve originals and verify exported attributes.
3. Add compact workspace actions with progress, cancellation, and explicit
   opening of the validated derived dataset as a new source/session.
4. Qualify raw/edited input, thinning-only, HAG-only, normalized Z, failure,
   cancellation, metadata preservation, large-source limits, and reopen.

## Implemented Request Boundary

`core/point_cloud/preparation.py` now defines immutable preparation intent:
Poisson/voxel-first thinning with positive finite spacing in source coordinate
units, or explicit add-HAG/normalize-Z actions. Ground-classification consent
is separate and defaults off. The contract does not select a scientific
ground model; managed execution must use and validate the existing planner.

Requests require a local SourceIdentity, absolute new LAS/LAZ paths, and a
free paired provenance path. EPT metadata and COPC output are rejected.
Construction/serialization are read-only; source hashing belongs in
`verify_input` in a worker. Runtime publication must repeat destination
checks and use no-replacement atomic publication; preflight alone cannot
eliminate a filesystem race.

`from_session` rejects active staged edits with guidance to export and open
the validated result first. It reads the existing journal and never changes
undo/redo history. Source identity/options/output form the deterministic
request signature. Schema validation rejects unknown request fields.

Thinning and normalization remain open Phase 34A4 requirements. This request
layer does not yet execute preparation or enable production controls.
