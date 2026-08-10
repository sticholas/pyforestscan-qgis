# Phase 28H Adaptive Performance Validation

Automated synthetic planning matrix with 8 GiB RAM, eight CPUs, 1-unit raster resolution, default EPT density:

| Case | Envelope | Derived units | Strategy |
| --- | --- | ---: | --- |
| Tiny | 100 x 100 | 1 | small safe request |
| Small | 400 x 400 | 1 | bounded single unit |
| Medium | 2,500 x 2,000 | 9 | bounded |
| Large | 11,000 x 6,700 | 84 | large bounded |
| Very large | 30,000 x 20,000 | 651 | very large bounded |

Tests also verify irregular exact filtering, network EPT serial safety, native LAS grouping, pilot growth/shrink behavior, and cache invalidation. These are planning results, not claims of live throughput. Source read, CHM, write, peak memory, and end-to-end timing remain **Not tested live** for Phase 28H.
