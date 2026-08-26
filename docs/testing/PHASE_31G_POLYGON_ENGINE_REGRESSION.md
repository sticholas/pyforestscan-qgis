# Phase 31G Polygon Engine Regression

## Original evidence

The failing click reported `Required dependency is not importable: pyforestscan.handlers`. The contemporaneous run folder contained no new coordinator job, locating the failure before coordinator creation. The raiser was the QGIS-side adapter dependency helper reached after an `auto` PBM readiness branch returned `None`.

## Fix contract

Polygon processing now asserts readiness before creating a logical job, freezes a runtime token, launches the coordinator with the managed executable and common environment, and validates the same contract in coordinator and workers. QGIS auto-mode cannot fall through to local scientific imports.

## Automated result

The two-source architecture is covered structurally: Polygon worker construction forces `pbm_backend`; the launcher records runtime identity; token and contract drift are rejected; and all advertised product mappings are present.

## Live result

A fresh QGIS run using the newly packaged ZIP is still required. Record managed executable, `pyforestscan.handlers.__file__`, coordinator PID creation, CHM output, and rumple output. Until that run is completed, CHM/Rumple live completion is **not confirmed** by Phase 31G automation.
