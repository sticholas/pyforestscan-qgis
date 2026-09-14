# Large-Scale LiDAR Architecture Research

## Deployment gate

Repository HEAD and the Phase 32M package are commit `a6182a2e8522462da17940d8311d83f8edd45b0d`. The installed default-profile plugin was inspected first and reports commit `5fa4c9fe1595966c81ba6c58ebba2ea2a27066bf`, build `e2547b3d40e39b93f2fc`, which is Phase 32L. An active QGIS process owns the current large coordinator, so the plugin was not overwritten or QGIS restarted. Current-job evidence below is valid historical Phase 32L telemetry, not a Phase 32M comparison.

## Current job truth

The source is one logical 110,008,858,527-point EPT dataset in EPSG:6635. The MultiPolygon has 77 source features, 8,962 vertices, about 811.6 km2 area, and about 4% envelope occupancy. Its plan stores 14,784 candidates, 957 required parents, and 13,827 polygon-excluded candidates.

At the first observed false-stall snapshot the coordinator was alive. A later 10.2-second sample showed:

- coordinator CPU: `1800.39 -> 1810.06` seconds;
- checkpoints: `73 -> 76`;
- TIFFs: `146 -> 152`;
- TIFF bytes: `24,508,655 -> 25,554,314`;
- heartbeat advanced by 11.7 seconds;
- bounded child PID recycled between subreads;
- progress advanced to 11 complete, 0 failed, 12 attempted, 945 pending.

Classification: **CPU_ACTIVE / SLOW_ACTIVE**, not deadlock. The fixed 120-second detector observed no parent transition while missing child-level progress. One completed 200 m read block contained 994,085 points and took 3.719 seconds end-to-end through bounded read, PyForestScan CHM, raster writes, and checkpoint.

## Adaptive progress model

Use child heartbeat, PID liveness, CPU delta, I/O delta, output growth, and child-stage timestamps. A parent without completion remains `RUNNING_ACTIVE` when any child signal advances; `WAITING_IO` requires live PID plus low CPU and measured I/O/network wait; `RUNNING_SLOW` means live progress beyond recent median; `NO_FORWARD_PROGRESS` requires no signal movement; `STALLED_CONFIRMED` requires a dead child or no movement beyond `max(3 * pilot, 2 * p95, 15 minutes)` plus a second confirmation interval.

ETA begins after three completed parents. Report median and p90 ranges, never a single precise completion time.

## Planning and locality evidence

Root `ept.json` is 7,915 bytes and read in 0.008 seconds. Root hierarchy is 55,495 bytes, 2,728 entries, and read in 0.004 seconds. At depth 5 it exposes 496 occupied XY cells about 4,717 m wide. Coarse hierarchy rejection reduces the 14,784 envelope candidates to 8,966 before polygon science, a 5,818-candidate (39.4%) reduction. Deeper proxy hierarchy reads are needed to approach the 1,122 m parent scale.

For the 957 required parent centers, row-major travel is about 4,858 km; Morton ordering is about 2,447 km, a 49.6% reduction. Grid alignment and output ownership do not change.

Separate contracts are required:

- `ReadBlock`: one bounded source fetch, cacheable and potentially shared;
- `ScienceBlock`: exact points passed to an unchanged PyForestScan API;
- `CheckpointTile`: durable aligned output ownership.

One read block may feed multiple science/checkpoint tiles only after equivalence testing proves identical point inclusion, halo, HAG, and raster values.

## Repository indexing

Folder repositories should retain the existing SQLite/RTree catalog keyed by path, size, mtime, bounds, CRS, point count, dimensions, and source identity. Selection loads the catalog immediately; a background incremental pass handles new, changed, and deleted paths. EPT is recognized by `ept.json` and stops recursive discovery. A periodic lightweight root metadata comparison is safer as the baseline Windows/UNC strategy than assuming every network filesystem reliably delivers watcher events.

## Plan compaction

Persist 957 required parents directly. Represent 13,827 excluded cells as row ranges or counts plus a grid signature rather than full work-unit dictionaries. Keep plan-level polygon, CRS, source, scientific assumptions, and parameters once. The observed frozen plan is 32.8 MB; compaction should target required extents plus compact exclusion evidence.

## Repository benchmark matrix

| Case | Evidence available | Result |
|---|---|---|
| Small LAS | Automated regression artifacts | Science unchanged; fresh live timing pending exact Phase 32M deployment |
| 104.8M-point LAS | Existing durable prepared-source/work-unit artifacts | Source identity and checkpoint route confirmed; fresh comparative timing pending |
| Small EPT polygon | Phase 32L live canary | Full CHM/mask/load previously passed |
| About 9,000 ha EPT | Phase 32K/32L durable evidence | 221 candidates / 109 required; complete rerun pending |
| 811 km2 sparse MultiPolygon | Active Phase 32L telemetry | 14,784 / 957; CPU_ACTIVE; no failures at observed sample |

Fresh cross-case performance conclusions are blocked until the installed plugin is Phase 32M and QGIS has fully restarted.
