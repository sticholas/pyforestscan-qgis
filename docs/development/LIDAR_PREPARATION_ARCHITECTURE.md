# LiDAR Preparation Architecture

Folder and polygon requests enter this same preparation engine after source selection. Polygon mode may select members with different preparation methods; existing HAG, class-2 Delaunay, and SMRF work can coexist when final product validity is preserved.

Phase 31A separates observed capabilities from required work. `LidarPreparationAssessment` records source identity, spatial-reference mode, coordinate units, dimensions, bounded classification evidence, DTM, product requirements, and scale. `HeightNormalizationPlanner` emits a signed `LidarPreparationPlan`; PBM executes its checkpointable steps and returns `PreparedLidarCapabilities`.

For standalone CHM/Rumple, PBM samples classification before loading product arrays. When preparation is required it runs a file-to-file PDAL pipeline, writes `preparation/<signature>/prepared_hag.laz`, validates completion, records provenance, and then calculates products from that artifact. The original source is never changed. A compatible second product reuses the checkpoint.

Precedence is existing HAG, supplied DTM, Delaunay from observed class 2, SMRF then Delaunay, then block. Vegetation classes 3/4/5 are not prerequisites. Products receive preparation method, signature, and provenance metadata.

Large preparation runs in managed PBM, not QGIS Python. Phase 31A deliberately does not split Delaunay normalization into independent tiles: buffered-core context and whole/tiled equivalence must be proven before adaptive normalization is enabled.

Phase 31B persists classification evidence independently from the spatial assignment. Resolving units rebuilds the plan without repeating the 50,000-point sample. Delaunay additionally checks ground occurrence across bounded strata; low overall ground percentage alone is not a rejection criterion.

Phase 31C freezes unit, unit basis, authority, CRS, and processing mode into product requests. PBM rehydrates that exact context. Preparation signatures distinguish assumed and trusted units; scientific HAG validation remains mandatory for both.
