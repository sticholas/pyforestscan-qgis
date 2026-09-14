# Phase 31A Large Raw LAS Regression

Production profile: `OlaaFR_RoadSite_Heli_Thin05_CropPC_Norm.las`, 104,819,538 points, about 750 x 702 source units, density 199.085, X/Y/Z plus Classification, no HAG, classification counts uninspected, CRS unknown, CHM and Rumple requested.

Expected sequence: detect missing HAG, sample bounded LAS windows in PBM, resolve trusted units, choose existing-ground Delaunay or validated SMRF then Delaunay, write one prepared checkpoint, and reuse it for CHM/Rumple.

The exact file was searched for on the available `D:` filesystem on 2026-08-26 and was not found, so no class-2 fraction or product result is claimed. With the supplied evidence, the honest plan is `NEEDS_USER_INPUT: SOURCE_UNITS_UNKNOWN`. Once units or CRS are assigned, bounded inspection can select the automatic path. Managed synthetic real-PDAL tests passed Delaunay HAG, CHM, Rumple, checkpoint reuse, and source-local meter-based Delaunay without assigning a CRS.

Whole-source file-to-file preparation runs in PBM. Adaptive tiled HAG remains deferred until buffered-ground seam equivalence is demonstrated.
