# Phase 32Q Concurrency Benchmark

## Managed benchmark

The authoritative test reused eight parent processing regions spanning the completed fixture's duration distribution (68.453 to 130.703 seconds in Phase 32P). Each parent executed its nine frozen bounded EPT reads, for 72 scientific reads per concurrency row. The source remained the same network-hosted EPT repository and every child used the sanitized PBM environment.

| Workers | Wall time | Speedup | Efficiency | RSS upper bound | EPT time | Failures | Equivalent |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 787.016 s | 1.000x | 100.0% | 1.42 GB | 165.733 s | 0 | Yes |
| 2 | 372.313 s | 2.114x | 105.7% | 2.79 GB | 86.418 s | 0 | Yes |
| 3 | 271.078 s | 2.903x | 96.8% | 4.08 GB | 87.576 s | 1 | No |

N=2 is the selected network-production ceiling. It completed all 72 reads, produced the same per-read raster hashes as N=1, and more than halved wall time. Its superlinear result reflects a warmed network/cache state, so 2.114x must not be projected mechanically onto the full fixture.

At N=3, one request that passed at N=1 and N=2 failed with SciPy/Qhull `QH6108 qhull internal error`. The failure is transient rather than a permanent input defect. Phase 32Q now classifies it explicitly, reduces adaptive capacity, and requeues it for isolated retry after active work drains. The row nevertheless fails the production safety/equivalence gate, so testing did not continue to parent-region N=4 or N=5.

## Bounded-read ramp pilot

Before the parent-region matrix, the same eight bounded requests passed at N=1 through N=5 with identical hashes and no failures. This pilot established that process isolation and machine memory were sufficient to approach the hard maximum, but it is not used to approve network production concurrency.

| Workers | Wall time | Speedup | Efficiency | RSS upper bound | EPT time | Failures |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 89.250 s | 1.000x | 100.0% | 1.33 GB | 12.014 s | 0 |
| 2 | 47.140 s | 1.893x | 94.7% | 2.55 GB | 12.531 s | 0 |
| 3 | 33.313 s | 2.679x | 89.3% | 3.74 GB | 13.492 s | 0 |
| 4 | 26.516 s | 3.366x | 84.1% | 4.91 GB | 15.698 s | 0 |
| 5 | 25.766 s | 3.464x | 69.3% | 5.64 GB | 16.822 s | 0 |

N=5 added only 2.9% throughput over N=4 while increasing network contention and reducing efficiency. The general hard maximum remains five for future/local evidence; network jobs start at one and ramp no higher than two.

## Failure and harness diagnostics

An initial N=1 harness attempt exited with Windows `0xC06D007F` after point loading because the standalone harness omitted the PBM `Library/bin` DLL path. Production workers already used the correct environment. The harness was corrected to call `build_processing_engine_environment`; the repeated N=1 row then passed all inputs. This was a benchmark-launch defect, not a plugin science failure.

## Full fixture status

Phase 32P remains the measured full-run control at 9,847.953 seconds. A full 109-region Phase 32Q rerun was not performed because it would add several hours of load to the shared network source. No full-fixture speedup is claimed. The representative parent benchmark demonstrates the selected N=2 policy; the next real user run will provide the first full-job comparison.
