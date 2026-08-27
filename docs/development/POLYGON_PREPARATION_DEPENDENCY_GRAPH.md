# Polygon Preparation Dependency Graph

The durable Polygon CHM/Rumple graph is:

```text
source assessment -> height preparation -> validation/checkpoint
  -> canary CHM work unit -> remaining CHM work units
  -> aligned CHM mosaic -> exact polygon mask -> final CHM

CHM buffered tiles -> Rumple halo calculation -> Rumple core mosaic
  -> exact polygon mask -> final Rumple raster and scalar summary
```

Preparation is source-scoped, not tile-scoped. CHM is calculated once and is also the supporting raster for Rumple. The global one-metre grid, buffered reads, core ownership, Rumple halo, and final exact mask are unchanged.

`SOURCE_PREPARATION_*`, `NORMALIZED_Z_VALIDATION_FAILED`, and `PREPARED_SOURCE_READ_FAILED` are global prerequisite failures. They stop before worker fan-out and are reported at `source_preparation`.
