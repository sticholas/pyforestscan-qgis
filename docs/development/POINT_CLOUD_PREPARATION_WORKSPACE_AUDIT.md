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

## Publication Boundary

`core/point_cloud/preparation_publication.py` adds attempt-owned staging and
exclusive hard-link publication, matching the existing editor export
primitive. The caller supplies scientific/file validation; only a VALIDATED
result can proceed. Input identity and destination availability are rechecked,
and the output hash and request signature are recorded in provenance.
Only attempt-created staging names are cleaned up.

Each published file is atomic and no-replacement. The output/provenance pair
is not a single filesystem transaction: a hard crash between the two links
can leave an orphan provenance file, which must not be mistaken for a
completed output. Unsupported hard-link filesystems fail closed rather than
fall back to overwriting. Managed-job recovery remains to be wired.

Tests cover success, failed validation, cancellation, source mutation,
concurrent output creation, staging-name collisions, directory retargeting,
and unsupported filesystems. Eight tests passed on Linux; seven passed on
Windows with one symlink-privilege skip. The first Windows run exposed an
fsync failure on a read-only handle; owned staging now uses r+b for flushing.
The focused suite ran 199 tests with 26 dependency skips and no failures.
These publication tests use byte fixtures, not scientific LAS validation.

Thinning and normalization remain open Phase 34A4 requirements. Request and
publication layers do not yet execute preparation or enable production controls.

## Array Execution Boundary

`core/point_cloud/preparation_execution.py` now composes the existing HAG
executor and official thinning filters for full-resolution arrays. Height
preparation precedes thinning so thinning does not remove ground support before
HAG calculation. Inputs are copied; add-HAG retains Z, while normalize-Z retains
original elevation in PFSOriginalZ and refuses an existing field of that name.
Normalized Z requires finite HAG at every point. Automatic ground classification
requires explicit consent, and unsupported planner modes fail closed.

The wrapper applies the scientific-runtime boundary and cancellation checks
between operations. Individual scientific filter calls are not interruptible
through this callback. It has no file loader or publisher and must not be
connected directly to the Qt event loop. A managed worker must still preflight
memory before array loading, verify original-source identity, validate every
retained output attribute and file metadata, and publish through the staging
contract. Copying arrays does not establish bounded-memory large-cloud support.

The preparation-focused tests run 29 checks on Linux and Windows managed
Python; Windows skips two symlink-privilege tests. New execution tests use fake
filter delegates to verify ordering, original-Z preservation, consent, invalid
HAG, cancellation, and invalid counts. These are contract tests, not new
scientific accuracy or real-file publication evidence. Workspace controls,
managed dispatch, real LAS/LAZ validation, and large-source limits remain open.

## Retained-Record Validation and Real Wrapper Evidence

Preparation now carries temporary PFSPreparationRecordId values referencing the
original full-resolution arrays. It rejects a conflicting source dimension,
lost/duplicate/out-of-range IDs, lost attributes, and unrelated source-attribute
changes. Thinning must preserve every prepared attribute, including normalized
Z and newly calculated HAG. Internal IDs are removed before the arrays leave
the wrapper. No new selection authority is introduced.

This validation currently allocates array copies, a sorted reference, and
identity-indexed comparisons. It is not a massive-cloud streaming solution;
the managed file loader must enforce a measured memory policy before use.

The Windows managed runtime ran six actual-filter/wrapper checks on the
20,000-point tiny.laz fixture using PyForestScan 0.4.1 and the sanitized
processing-engine environment. Evidence is in the local artifact directory
`artifacts/phase34a4/preparation-wrapper-02/preparation-evidence.json`.

| Wrapper operation | Retained points | Observed seconds |
| --- | ---: | ---: |
| Voxel-first, 0.5 source units | 3,931 | 0.031 |
| Existing-ground Delaunay HAG | 20,000 | 0.094 |
| Normalize Z, then Poisson 0.5 source units | 1,369 | 0.109 |

Normalized-Z thinning operates in normalized coordinates; it is therefore
not equivalent to thinning original XYZ first. The direct original-coordinate
Poisson check retained 1,643 points. This operation order must be explicit in
the eventual workspace controls and output provenance.

All retained original attributes matched, normalized Z matched HAG, temporary
IDs were absent from returned arrays, and input arrays and file remained
unchanged. Source SHA256:
`4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866`.
Each wrapper's HAG provenance has a separate attempt directory. Timings are
single bounded-fixture observations, not throughput benchmarks or scientific
accuracy evidence. No derived LAS/LAZ was published by this harness.

The preparation suite now has 33 passing tests on Linux; Windows runs the same
33 with two symlink-privilege skips. Tests also reject malformed filters that
alter coordinates/heights, duplicate retained records, or discard identities.
