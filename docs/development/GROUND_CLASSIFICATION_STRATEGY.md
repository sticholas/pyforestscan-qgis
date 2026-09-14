# Ground Classification Strategy

`ClassificationInspectionService` reads bounded, storage-stratified LAS windows. It records sample count, class-2 observation, estimated fraction, vegetation classes, method, confidence, warnings, and sampled counts. This avoids copying a 100-million-point source into QGIS simply to answer whether class 2 is present.

If class 2 is observed, preparation uses Delaunay HAG directly. If it is absent from a valid Classification dimension, PBM may run PyForestScan's PDAL SMRF wrapper and validates generated ground before HAG. Sample absence is not described as proof that the full source has no ground.

SMRF materially changes classification, so its method, parameters, unit interpretation, source signature, and warnings are persisted. The source LAS is never overwritten. Vegetation classes 3/4/5 are informative but do not block CHM or Rumple.

