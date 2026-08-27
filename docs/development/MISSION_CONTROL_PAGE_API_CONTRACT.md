# Mission Control Page API Contract

## Phase 32C semantic updates

`SettingsPage.set_processing_engine_state(...)` owns the persistent setup/recovery action. `BatchPage.set_processing_engine_state(...)` owns the compact Process-page setup intervention, and `BatchPage.set_spatial_intervention(...)` owns source-specific CRS/units intervention. Mission Control propagates completed engine state through signals; pages do not reach into one another's child widgets.

## Rule

Controllers update pages through semantic methods. They do not write another page's private labels or depend on a particular card layout.

## Engine and Status APIs

- `SettingsPage.current_processing_engine_state()` obtains the optional quick engine projection after UI construction.
- `SettingsPage.set_processing_engine_state(engine)` updates the Tools & Setup card.
- `EnvironmentPage.set_processing_engine_state(engine)` updates readiness copy without running dependency checks.
- `BatchPage.set_processing_engine_state(engine)` controls setup guidance and Process availability while preserving selections.
- `BatchPage.set_smart_status(headline, detail)` updates the shared workflow summary.
- `MissionControlDock._update_status_bar()` consumes cached `ApplicationAvailability`; it performs no engine read.

## Lifecycle APIs

- `MissionControlDock.prepare_for_unload()` enters `DESTROYING`, stops page timers, and disconnects engine-state delivery.
- Engine events received during `CREATING` are deferred.
- Engine events received during `DESTROYING` are ignored.

## Retained Deliberate Access

Mission Control still reads a small set of form values for session serialization and connects public Qt signals. Those controls are deliberate compatibility surfaces, not cross-page status projections. New status or readiness behavior must use a semantic method.

The removed `smart_system_status_label` is not part of this contract and must not be recreated as a hidden compatibility widget.
