# PyForestScan Runtime Contract

Setup records callable signatures as well as function presence and computes a smoke result for every advertised product family. PyForestScan `0.4.1` remains the exact supported version; missing handlers or a changed mapped API prevents READY.

The supported production target is PyForestScan `0.4.1`. `core/backend/runtime_manifest.py` defines the authoritative module, function, dependency, and product-capability contract.

Required modules are `pyforestscan`, `pyforestscan.calculate`, `pyforestscan.filters`, `pyforestscan.handlers`, and `pyforestscan.process`. Required handlers include `read_lidar`, `create_geotiff`, and `write_las`. Calculation and filter functions cover CHM, canopy cover, PAD, PAI, FHD, rumple, DTM, point density, voxel statistics, ground preparation, HAG, and supported preprocessing.

The verifier records module paths and package versions and checks function presence before READY. Its stable contract hash excludes volatile PID and working-directory values. Jobs reject an executable, protocol, function contract, or product-capability hash different from the frozen pre-launch token.

The dependency manifest covers PyForestScan, PDAL, Rasterio, NumPy, GDAL, SciPy, Shapely, PyProj, and pandas, with required/optional status, import probes, version policy, and affected products. Compiled geospatial dependencies remain conda-forge owned; the known-compatible PyForestScan package remains installed by the managed setup transaction.
