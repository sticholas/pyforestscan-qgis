# Phase 31H Engine State Convergence

## Original contradiction

Repair and Verify Backend updated legacy backend status/UI. The engine card read `processing_engine.json`; Process created a new verifier and discarded its token; execution created another verifier/token. These owners could disagree after installation/config timestamp changes, plugin/backend build skew, or a different loaded plugin package.

## Automated evidence

- One shared service is returned for one engine root.
- READY publishes a token containing the same engine ID, executable, fingerprint, contract, protocol, runner, plugin, dependency, and capability identity.
- Repeated Process token requests do not rerun verification.
- Removing the handlers sentinel changes the fingerprint.
- One hundred alternating Ready/Repair transitions are observed in order.
- Every production UI/Advanced entry point bans default/auto adapters.

## Live evidence boundary

The available Windows engine is probed during Phase 31H packaging. A clean QGIS Polygon click remains a manual gate for coordinator creation and CHM/Rumple completion.
