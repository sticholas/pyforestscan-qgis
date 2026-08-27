# UI Startup Resilience

## Invariant

Mission Control is available independently from scientific processing. Plugin activation, dock construction, navigation, settings, diagnostics, and prior-result access require only QGIS/PyQt, plugin-local modules, and lightweight persisted state.

The UI must not import or execute PyForestScan, PDAL, Rasterio, managed Python, or the PBM runner merely to open.

## Lifecycle

`MissionControlDock` uses three states:

1. `CREATING`: pages are being constructed and engine events are retained as one pending projection.
2. `READY`: semantic page projections are accepted.
3. `DESTROYING`: plugin unload rejects late engine events and stops page-owned timers.

Construction order is models and lightweight state, complete page construction, page registration, signal wiring, session restoration, initial cached projection, `READY`, then a zero-delay lightweight engine-state resolution. Engine lookup failures are contained and displayed as status unavailable; they cannot tear down the dock.

Closing the dock only hides it and saves session state. Plugin unload calls `prepare_for_unload()` before Qt deletion.

## Availability Boundary

`ApplicationAvailability.ui_available` remains true when `processing_available` is false. The Process action is disabled and setup guidance appears, while all non-processing UI remains usable.

Full environment validation runs only when explicitly requested. An engine-state event updates Environment, Process, Tools & Setup, Home, and the footer through semantic projections without launching the full Environment Check.

## Startup Failure Containment

Only optional engine-state resolution is contained. General programming errors still fail tests rather than being hidden by broad `getattr` or exception handling. The packaged QGIS smoke calls the exact `_update_status_bar()` path and verifies missing, repair-required, failed, and ready engine projections.
