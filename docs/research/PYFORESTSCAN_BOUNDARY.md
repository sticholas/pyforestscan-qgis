# PyForestScan Boundary and Compatibility

## Audited runtime

The managed backend was inspected on 2026-09-01 and contains PyForestScan `0.4.1`. Its public modules expose `handlers.read_lidar`, filtering/HAG helpers, voxel assignment, CHM, canopy cover, PAD, PAI, FHD, Rumple, DTM, point density, and voxel statistics. The official [API documentation](https://pyforestscan.sefa.ai/api/calculate/) remains the parameter authority.

| Area | PyForestScan 0.4.1 contract | Plugin responsibility |
|---|---|---|
| Native input | `read_lidar`; validator documents LAS/LAZ | Prepare bounded EPT/COPC derivatives only when dimensions/provenance are preserved |
| HAG | Existing `HeightAboveGround`, Delaunay ground method, or DTM | Select and record supported method; never substitute raw `Z` |
| CHM | `calculate_chm(arr, voxel_resolution, interpolation, ...)` | Bounded read, halo, aligned core ownership, mosaic, mask |
| PAD/PAI/FHD | Official calculate functions and parameters | Memory admission and output serialization |
| Rumple | `calculate_rumple(chm, cell_resolution, min_height)` | Halo/core partitioning with equivalence tests |
| DTM | `generate_dtm(ground_points, resolution)` | Ground-input preparation and georeferencing |
| PDAL | Used by handlers and filters | Reader bounds, process isolation, diagnostics |

The audited source accepts LAS/LAZ directly. EPT and COPC are PDAL-readable formats, but direct support must not be inferred to be an official PyForestScan handler contract. The plugin’s EPT route therefore performs bounded PDAL input preparation and then calls supported PyForestScan science.

The authoritative public behavior is documented by the [PyForestScan project site](https://pyforestscan.sefa.ai/), [handlers API](https://pyforestscan.sefa.ai/api/handlers/), [filters API](https://pyforestscan.sefa.ai/api/filters/), and upstream [GitHub repository](https://github.com/iosefa/PyForestScan).
