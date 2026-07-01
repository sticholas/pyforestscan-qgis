# PyForestScan Full Site Crawl

Phase 20E rescraped the official site navigation from `https://pyforestscan.sefa.ai/` and recorded every internal page found. Network crawl succeeded on July 1, 2026.

| URL | Title | Functions/workflows mentioned | Examples shown | Plugin status | Deferred reason |
| --- | --- | --- | --- | --- | --- |
| https://pyforestscan.sefa.ai/ | PyForestScan Documentation | overview, installation links, feature list | project overview, examples | Implemented by plugin architecture; no toolbox function | No |
| https://pyforestscan.sefa.ai/installation/ | Installation | PDAL, GDAL, pip, Docker | dependency installation examples | Documented in dependency strategy | No |
| https://pyforestscan.sefa.ai/usage/getting-started-import-and-preprocess/ | Importing, Preprocessing, and Writing Data | read_lidar, remove_outliers_and_clean, classify_ground_points, add_height_above_ground, write_las | import/preprocess/write workflow | Implemented through Normalize Heights and Preprocess Point Cloud | No |
| https://pyforestscan.sefa.ai/usage/digital-terrain-models/ | Digital Terrain Models | filter_select_ground, generate_dtm, create_geotiff, plot_metric | DTM creation and plotting | Generate DTM implemented; plot_metric deferred to QGIS-native styling | plot_metric uses matplotlib outside QGIS layer model |
| https://pyforestscan.sefa.ai/usage/forest-structure/intro/ | Forest Structure Introduction | assign_voxels, forest metric concepts | forest metric workflow | Implemented by Metrics tools and Mission Control | No |
| https://pyforestscan.sefa.ai/usage/forest-structure/chm/ | Canopy Height Models | calculate_chm, interpolation, valid region, clean edges | CHM examples | CHM implemented | No |
| https://pyforestscan.sefa.ai/usage/forest-structure/rumple/ | Rumple Index | calculate_rumple, cell_resolution, min_height | rumple from CHM | Rumple implemented as CSV scalar | No |
| https://pyforestscan.sefa.ai/usage/forest-structure/pad/ | Plant Area Density | assign_voxels, calculate_pad, voxel_height, beer_lambert_constant, drop_ground | PAD example | PAD implemented as multi-band GeoTIFF | No |
| https://pyforestscan.sefa.ai/usage/forest-structure/pai/ | Plant Area Index | calculate_pai, voxel_height, min_height, max_height | PAI example | PAI implemented | No |
| https://pyforestscan.sefa.ai/usage/forest-structure/fhd/ | Foliage Height Diversity | calculate_fhd, voxel_height, min_height, max_height | FHD example | FHD implemented | No |
| https://pyforestscan.sefa.ai/examples/getting-started-importing-preprocessing-dtm-chm/ | Example: Getting Started | read_lidar, filters, generate_dtm, calculate_point_density, calculate_chm | end-to-end getting-started notebook | Covered by Input/I/O, Preprocess, Terrain, Metrics tools | No |
| https://pyforestscan.sefa.ai/examples/calculate-forest-metrics/ | Example: Calculate Forest Metrics | assign_voxels, CHM, PAD, PAI, cover, FHD, plot helpers | forest metric example | Metric functions implemented; plot helpers deferred | QGIS-native visualization preferred |
| https://pyforestscan.sefa.ai/examples/working-with-large-point-clouds/ | Example: Working With Large Point Clouds | EPT, bounds, crop polygon, process_with_tiles | large EPT workflow | Read options partially implemented; process_with_tiles deferred | Needs QGIS-safe tiling wrapper |
| https://pyforestscan.sefa.ai/benchmarks/ | Benchmarks | runtime and memory examples | benchmark tables | Documented only | Not a Processing operation |
| https://pyforestscan.sefa.ai/api/calculate/ | API: calculate | all calculate functions and parameters | function API reference | Implemented for safe metric functions | No |
| https://pyforestscan.sefa.ai/api/filters/ | API: filters | all public filter functions | filter API reference | Implemented in Preprocess Point Cloud | No |
| https://pyforestscan.sefa.ai/api/handlers/ | API: handlers | read_lidar, write_las, create_geotiff, CRS/polygon helpers | handler API reference | Core I/O implemented; standalone helpers deferred | QGIS-native CRS/vector UX preferred |
| https://pyforestscan.sefa.ai/api/pipeline/ | API: pipeline | pipeline helpers | page returned internal server error during audit | Installed source inspected; helpers internal | Internal underscored helpers |
| https://pyforestscan.sefa.ai/api/process/ | API: process | process_with_tiles parameters | large EPT tiling API | Deferred | Needs dedicated safe workflow |
| https://pyforestscan.sefa.ai/api/visualize/ | API: visualize | plot_2d, plot_metric, plot_pad | matplotlib plots | Deferred / QGIS-native preferred | QGIS has stronger native visualization |
| https://pyforestscan.sefa.ai/contributing/ | Contributing | project process | contribution instructions | Not plugin API | No |
| https://pyforestscan.sefa.ai/code_of_conduct/ | Code of Conduct | project process | community policy | Not plugin API | No |

## Crawl Notes

- The crawl found the home, installation, usage, examples, benchmarks, API, contributing, and code-of-conduct pages listed above.
- The pipeline API page was linked by the docs site but returned an internal server error during earlier API inspection; installed source was used for pipeline status.
- No additional public classes were found in the installed source.
