# Adaptive Processing Planner

Phase 28H replaces fixed EPT window widths with `AdaptiveProcessingPlan`. Inputs include envelope and exact-polygon area, compactness, source type, native partitions, point density, output resolution, HAG method, available RAM, CPU count, storage location, and optional performance history.

The planner maximizes safely efficient units. A small-safe request uses one bounded read and bypasses work-unit mosaicing. Medium work uses a few larger units. Large and very-large requests add bounded windows without a preferred count or a 120-unit cap. LAS/LAZ native footprints remain first-level boundaries; EPT uses logical bounded queries and never enumerates nodes.

Stage 1 is metadata-only. Stage 2 accepts a representative `PilotMeasurement` and increases or decreases linear unit scale from measured duration and peak memory while recalculating safe concurrency. Performance history is advisory and keyed by repository, source type, product, resolution, HAG method, density band, backend, and algorithm version.

Current limitation: the calibration contract and cache are implemented and tested, but automatic live PBM pilot capture/replanning has not been validated interactively. Initial plans remain conservative and scientifically equivalent.
