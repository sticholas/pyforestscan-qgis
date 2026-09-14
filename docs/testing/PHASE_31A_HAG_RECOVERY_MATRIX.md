# Phase 31A HAG Recovery Matrix

| Height state | Ground/DTM | CRS/units | Result |
|---|---|---|---|
| Existing HAG | Any | Source-local allowed | `USE_EXISTING_HAG`; no preparation |
| Missing HAG | Compatible DTM | Known alignment | `DTM_EXISTING` |
| Missing HAG | Class 2 sampled | Trusted linear units | `DELAUNAY_FROM_EXISTING_GROUND` |
| Missing HAG | No class 2 sampled, Classification present | Trusted linear units | SMRF, validate class 2, Delaunay |
| Missing HAG | No supported ground/DTM | Any | Block with recommendation |
| Missing HAG | Ground present | Source-local units unknown | `NEEDS_USER_INPUT` / `SOURCE_UNITS_UNKNOWN` |
| Missing HAG | Polygon, CRS unknown | Any | Block before spatial alignment |

Automated tests cover LAS planning, conceptual 104,819,538-point scale, bounded sampling, DTM precedence, no-vegetation behavior, quality checks, checkpoint identity, readiness semantics, and existing-HAG continuity. The managed Windows PBM tests create real LAS fixtures, generate Delaunay HAG, create CHM/Rumple, verify second-product checkpoint reuse, and verify a no-CRS source with trusted meter units produces a source-local CHM without an assigned CRS.

A separate managed PBM run used a valid LAS whose points were all initially class 1. Bounded inspection selected `AUTO_CLASSIFY_GROUND_THEN_DELAUNAY`; PDAL SMRF produced ground, Delaunay HAG completed, and CHM finished successfully with provenance and no manual preprocessing.
