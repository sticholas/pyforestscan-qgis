# PyForestScan Usage and Examples Audit

| Page | Workflow | Plugin implementation | Deferred items | Notes |
| --- | --- | --- | --- | --- |
| [Importing, Preprocessing, and Writing Data](https://pyforestscan.sefa.ai/usage/getting-started-import-and-preprocess/) | read_lidar, remove_outliers_and_clean, classify_ground_points, add_height_above_ground, write_las | Implemented through Normalize Heights and Preprocess Point Cloud | No | import/preprocess/write workflow |
| [Digital Terrain Models](https://pyforestscan.sefa.ai/usage/digital-terrain-models/) | filter_select_ground, generate_dtm, create_geotiff, plot_metric | Generate DTM implemented; plot_metric deferred to QGIS-native styling | plot_metric uses matplotlib outside QGIS layer model | DTM creation and plotting |
| [Forest Structure Introduction](https://pyforestscan.sefa.ai/usage/forest-structure/intro/) | assign_voxels, forest metric concepts | Implemented by Metrics tools and Mission Control | No | forest metric workflow |
| [Canopy Height Models](https://pyforestscan.sefa.ai/usage/forest-structure/chm/) | calculate_chm, interpolation, valid region, clean edges | CHM implemented | No | CHM examples |
| [Rumple Index](https://pyforestscan.sefa.ai/usage/forest-structure/rumple/) | calculate_rumple, cell_resolution, min_height | Rumple implemented as CSV scalar | No | rumple from CHM |
| [Plant Area Density](https://pyforestscan.sefa.ai/usage/forest-structure/pad/) | assign_voxels, calculate_pad, voxel_height, beer_lambert_constant, drop_ground | PAD implemented as multi-band GeoTIFF | No | PAD example |
| [Plant Area Index](https://pyforestscan.sefa.ai/usage/forest-structure/pai/) | calculate_pai, voxel_height, min_height, max_height | PAI implemented | No | PAI example |
| [Foliage Height Diversity](https://pyforestscan.sefa.ai/usage/forest-structure/fhd/) | calculate_fhd, voxel_height, min_height, max_height | FHD implemented | No | FHD example |
| [Example: Getting Started](https://pyforestscan.sefa.ai/examples/getting-started-importing-preprocessing-dtm-chm/) | read_lidar, filters, generate_dtm, calculate_point_density, calculate_chm | Covered by Input/I/O, Preprocess, Terrain, Metrics tools | No | end-to-end getting-started notebook |
| [Example: Calculate Forest Metrics](https://pyforestscan.sefa.ai/examples/calculate-forest-metrics/) | assign_voxels, CHM, PAD, PAI, cover, FHD, plot helpers | Metric functions implemented; plot helpers deferred | QGIS-native visualization preferred | forest metric example |
| [Example: Working With Large Point Clouds](https://pyforestscan.sefa.ai/examples/working-with-large-point-clouds/) | EPT, bounds, crop polygon, process_with_tiles | Read options partially implemented; process_with_tiles deferred | Needs QGIS-safe tiling wrapper | large EPT workflow |
| [Benchmarks](https://pyforestscan.sefa.ai/benchmarks/) | runtime and memory examples | Documented only | Not a Processing operation | benchmark tables |

## Product Decision

Mission Control remains the guided interface. The Processing Toolbox is now the expert interface and no longer registers Dataset Explorer, Product Planner, or Forest Metrics Pack as top-level toolbox algorithms.
