# Phase 31K Windows Background Processing

Live-test Setup, Recheck, folder processing, polygon processing, and cancellation on clean Windows QGIS. Expected result: no console, PowerShell, or Command Prompt windows appear.

Automated coverage verifies centralized Windows no-console flags and terminal heartbeat closure. The code audit found no production `shell=True`; coordinator child jobs, GDAL capability checks, backend execution, installers, and guarded batch workers use the shared hidden-process policy.

Soak states to verify in QGIS are success, scientific failure, cancellation, presentation warning, and recovered completion. In every terminal state the coordinator exits, heartbeat records `active: false`, and QGIS remains responsive.
