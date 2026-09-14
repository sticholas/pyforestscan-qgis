# Phase 31I Real Manifest Regression

The August 27 polygon manifest reported READY, EPSG:6635, CHM plus Rumple, two selected LAS sources, and 209,639,076 estimated points. It contained no processing runtime identity. Work-unit IDs restarted at `wu-0001`. `recent_error.json` had an empty attempt ID and incorrectly labeled the prelaunch failure `batch_terminal`.

The local-LAS branch in `execute_polygon_batch()` called `PyForestScanAdapter.normalize_heights()` inside QGIS Python before coordinator creation. `_import_required()` rejected that scientific import at the runtime boundary and emitted "Processing Engine needs repair before this job can start." Independent verifier and readiness calls had discarded the Prerun identity, so diagnostics could not name a token field.

The production-shaped regression uses Polygon mode, CHM plus Rumple, EPSG:6635 assumed coordinate space, one canonical prepared source, a 104,819,538-point estimate, a frozen READY token, and globally unique source-qualified work units.

The launch path now creates the coordinator workspace, assigns an attempt ID, writes runtime comparison/trace artifacts, and starts the coordinator with the Prerun token. Large plans run one bounded canary and continue automatically when it passes.
