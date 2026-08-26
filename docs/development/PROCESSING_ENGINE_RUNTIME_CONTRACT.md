# Processing Engine Runtime Contract

Phase 31H persists engine ID, runner and plugin build hashes, dependency manifest hash, all-product capability hash, callable signatures, smoke results, and the exact executable/fingerprint token. Critical package files invalidate stale cached readiness.

Phase 31G adds the stable contract hash, plugin build identity, full PyForestScan function probes, product capabilities, and `ProcessingRuntimeToken`. Volatile process values remain diagnostic but do not change the stable hash. Every managed worker validates its executable, protocol, and contract against the pre-launch token.

Contract version `1` records the backend protocol, plugin and runner identity, Python executable/version, process identity, working directory, module paths and versions, environment fingerprint, and verification time.

Required imports are:

- `pyforestscan`
- `pyforestscan.handlers`
- `pyforestscan.calculate`
- `pyforestscan.filters`
- `pyforestscan.process`
- `pdal`
- `rasterio`
- `numpy`
- `osgeo.gdal`

The runtime probe executes through the managed backend Python with sanitized environment variables and backend-local `PATH`, `GDAL_DATA`, `PROJ_DATA`, and `PROJ_LIB`. The reported executable must match the launch executable. Missing modules, identity mismatch, or incompatible protocol prevent `READY`.

`processing_engine.json` is a cache, not authority. It is invalidated when the executable/config fingerprint or contract version changes. Full verification after setup rewrites it atomically.

An inability to update only the optional cache is retained as `cache_write_error` diagnostics and does not override a successful live contract. Installer/setup permission validation remains blocking before environment modification.
