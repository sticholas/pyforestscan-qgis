# Product Parameter Registry

Phase 31H preserves this registry as the only plugin-supported parameter/default catalog. Runtime signature reporting provides setup-time evidence that each mapped function remains available; no setup code introduces product defaults.

`core/product_parameters.py` is the central catalog for supported scientific controls. Each entry records the product, public parameter name, type, plugin default, valid range or choices, units, description, advanced visibility, PyForestScan target function, and target argument.

The registry covers CHM resolution, canopy threshold, PAD/PAI/FHD vertical settings, rumple controls, DTM resolution, point-density resolution, and voxel-statistic controls. `parameters_for_product()` is the common query API.

UI, request serialization, adapter translation, and output provenance should consume this registry as legacy defaults are retired. A mapped upstream signature change is an engine compatibility failure during verification, not a surprise during a real job.
