# Phase 32O Sparse EPT Execution

## Scope

Phase 32O replaces global-envelope candidate generation for polygon EPT/COPC plans with component-first sparse planning. It changes execution logistics only. PyForestScan remains the scientific authority and its calculations and parameters are unchanged.

## Exact Regression Fixture

- Job signature: `2ddc973459416e91a47265d5ea18f313da6640f56dcd6b8f8914312e24d25bb0`
- Legacy plan: `e87e474a99e148306c0760f8d67f9ff78ee56293aa07e3648447820539f60fd2`
- Geometry: 27 components, 414.636 ha
- Envelope: 51,297 m by 83,136 m
- Legacy representation: 3,450 candidates, 42 executable, 3,408 persisted skips
- Legacy job tree: 6,464 files, 4,203 directories, 107,550,571 bytes
- Legacy frozen plan: 7,801,348 bytes
- Terminal result: 2 complete, 1 valid NoData, 40 failed, 937.562 seconds

The dominant terminal failure was not planning overhead. The installed plugin directory disappeared while the detached job was running. Most workers failed because `backend_runner/ept_chm_subread.py` could no longer be opened; one worker also failed to import `pyforestscan_qgis.core.chm_work_unit_execution`. One successful block spent 493.609 seconds in bounded read plus CHM, 0.110 seconds extracting its aligned core, and 0.015 seconds hashing/checkpointing.

## New Planner

Planning begins with immutable `NormalizedPolygonGeometry.parts`. Each part has a stable signature and exact area. A safe component is represented directly; only components exceeding adaptive point, memory, or raster limits are subdivided. Every proposed region is aligned to the original global grid and must pass exact polygon intersection before a `WorkUnit` exists.

For local EPT datasets, the cached root hierarchy occupancy index rejects unoccupied regions before work-unit creation. Missing or unreadable hierarchy metadata fails open. Nearby components receive deterministic transport-cluster identities without altering or merging scientific geometry. Executable regions are ordered by Morton code for locality.

`ReadBlock`, `ScienceBlock`, and `CheckpointTile` identities are distinct fields even where the current safe implementation maps them one-to-one. This preserves fresh-process isolation and permits later read sharing without changing scientific block ownership.

## Measured Result

The exact fixture produces:

- 27 components and 26 transport clusters
- 50 candidate/executable regions
- 50 ReadBlocks, ScienceBlocks, and CheckpointTiles
- zero skipped objects or skipped status files
- 0.006 seconds planning time
- 111,325-byte serialized plan
- 50 projected status files

This is a 98.6% reduction in candidate objects and a 98.6% reduction in projected status files. The detailed machine-readable evidence is in `PHASE_32O_CURRENT_FIXTURE.json`.

## User Experience

Normal preflight now reports selected area, separate areas, automatic strategy, and processing regions. Candidate-grid and outside-cell counts are removed. Advanced diagnostics retain component and block counts plus the aggregate number of empty envelope regions that were never materialized.

## Scientific Invariants

- Exact polygon geometry and final mask are unchanged.
- The global raster origin, resolution, rows, and columns remain unchanged.
- CHM retains the 50 m support buffer.
- PyForestScan API calls and formulas are unchanged.
- Existing checkpoint recovery remains keyed by stable executable-region IDs.

## Storage Decision

Phase 32O removes status files for known-empty cells. It does not migrate active recovery state to SQLite or move established run folders while detached coordinators may still reference the legacy contract. `job_state.sqlite`, managed `%LOCALAPPDATA%` job relocation, bounded read-through caching, and shared ReadBlock transport remain follow-up migrations requiring explicit backward-compatible recovery tests.

## Live QA Gate

Live QGIS Phase 32O execution was blocked. QGIS 3.44.13 processes and PBM Python processes were active, but no installed default-profile `build_info.json` remained. The exact legacy job proves its plugin runner files were removed during execution. Overwriting or restarting that environment would violate the build-identity and active-job safety gate.

Required follow-up after QGIS is closed:

1. Deploy the packaged Phase 32O build to the default profile.
2. Verify commit, package build ID, engine contract, and runtime generation in diagnostics.
3. Complete the 100 m EPT canary.
4. Start and measure several regions of the 414.6 ha fixture.
5. Smoke-plan the 811 km2 sparse fixture.
6. Inspect user output and managed recovery storage before enabling relocation or cache changes.
