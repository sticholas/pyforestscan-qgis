# Rumple Product Audit

Before Phase 30A, guided, adapter, PBM, pipeline, Results, and Advanced Toolbox paths treated Rumple as a scalar CSV. `localized_rumple.py` contained a dormant moving-window experiment with a 75% cell-validity rule, but it had no georeferencing, writer, Results contract, or adaptive integration.

The reusable parts were upstream-compatible two-triangle geometry and the adapter's current-session CHM cache. The CSV path is retained only for serialized-plan compatibility. New plans request `rumple.tif`; old CSV records infer `rumple_summary` and cannot auto-load as rasters.

The authoritative core is now `calculate_local_rumple_surface`. Product/output behavior is owned by `product_capabilities.py`; adapter and Advanced Toolbox call that core rather than implementing independent mathematics.
