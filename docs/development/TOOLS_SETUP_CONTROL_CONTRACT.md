# Tools & Setup Control Contract

## Purpose

Tools & Setup answers two normal-user questions: **Is the Processing Engine ready?** and **Where should outputs go?** Specialist spatial-reference repair and technical evidence remain available without competing with that path.

## Authoritative Controls

- **Set Up / Repair** is the only engine-changing action. Its label is derived from `ProcessingEngineStateModel`; it is hidden when Ready.
- **Recheck Processing Engine** performs read-only verification and refreshes every engine-state projection.
- **Open Diagnostics** reveals the consolidated technical report and log preview. It does not install, repair, or launch processing.
- **Browse** changes only the default output folder.
- **Open Mission Control at QGIS startup** changes only the startup preference.
- Trusted-unit assignment actions modify only the user-local spatial assignment store and do not rewrite source LiDAR.

## State Ownership

`ProcessingEngineService.processing_engine_state()` is the single source for status, readiness, repair requirement, and the contextual setup action. UI labels are projections and cannot authorize processing. Setup completion publishes the verified runtime token through the existing transaction; Recheck only refreshes the projection.

The internal recent-item value bounds recent workspace display. It must not be read by batch discovery, polygon planning, work-unit scheduling, output finalization, or any scientific execution path.

## Disclosure Rules

- Processing Engine is expanded and compact.
- Advanced Settings is always visible.
- LiDAR Spatial Reference is collapsed by default.
- Troubleshooting and Technical log are collapsed by default.
- Technical package names, paths, compatibility reports, versions, and logs belong only in diagnostics.

## Compatibility

Legacy helper methods may remain callable for compatibility and tests, but they must not create duplicate visible controls. New setup or support actions must be added to this contract before appearing on the normal page.

Mission Control may call `current_processing_engine_state()` after its lifecycle reaches Ready and may project state through `set_processing_engine_state()`. It must not mutate labels or other child widgets directly.
