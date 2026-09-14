# HAG Failure Investigation

Phase 28E-Stabilization retains the August 6, 2026 evidence without asserting an unproven root cause. Two 120-unit EPT CHM runs completed only units 1 and 2. Neighboring units then returned `All points collinear`; one returned empty arrays. Run 2 also produced a native `pdalcpp.dll` access violation. QGIS later crashed in `ntdll.dll` while a PBM worker remained active.

## Measured Comparison

| Unit | Outcome | Read bounds | Evidence |
| --- | --- | --- | --- |
| wu-0001 | Complete | 204938.524764-205788.524764, 2216217.04299-2217067.04299 | Buffered and core CHM exist. |
| wu-0002 | Complete | Next adjacent 850 m window | Buffered and core CHM exist. |
| wu-0003 | HAG collinear | 206438.524764-207288.524764, 2216217.04299-2217067.04299 | `handlers.read_lidar(..., hag=True)` raised `All points collinear`. |
| wu-0015 | Empty read | Recorded worker request | PyForestScan returned empty point arrays. |
| run-2 wu-0013 | Native crash | 213938.524764-214788.524764, 2216217.04299-2217067.04299 | Worker PID 27908 faulted in `pdalcpp.dll`, code `0xC0000005`. |

The earlier workers did not record point/classification distributions, so an alternate HAG method is not selected. `HagWindowSuitability` now defines the required point, rank, ground, range, coverage, dimension, and reason fields for inspect-first integration. Collinear and empty reads are deterministic and nonretryable.

## Unproven

OOM is not established. A common cause for the QGIS and PDAL crashes is not established. Ground classification quality, duplicate XY behavior, and loaded DLL provenance require controlled live probing.

## Phase 28F correction

Validated existing HeightAboveGround now controls execution with hag=False. Source-aware CHM no longer exact-crops points before rasterization. The real failing windows still require live rerun.
