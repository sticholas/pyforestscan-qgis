# Phase 34 protected baseline

- Commit: `3962a42aed9f4b65e4cc6cebebd45a256b1395e3`.
- Local internal tag: `viewer-editor-baseline-v0.2.0-beta.1`; not a public release.
- Version: `0.2.0-beta.1`.
- Baseline ZIP: `dist/pyforestscan_qgis-v0.2.0-beta.1.zip`.
- SHA256, independently checked before Phase 34 packaging:
  `08e5bd02fbdc62b18210d33ac0110414548c25ba4e5169cb408df7b5cee90f4e`.
- Previous phase test record: 1,015 tests run, seven skipped, no failures.
  This is historical evidence, not a fresh Phase 34 test run.
- Existing CHM canary recorded SHA256:
  `9c8d9c3ad11cebde5814c5df0222dca63c37326a78617058919d38756dfcdcee`.
  It was not scientifically rerun for this contract-only milestone.
- Protected products: CHM, DTM, PAD, PAI, FHD, Canopy Cover, Rumple raster,
  Point Density. Preserve Rumple summary export as well.
- Protected engine: verified managed Python, runtime-token validation,
  sanitized child environment, hidden Windows subprocesses, durable job state.
  Do not import scientific packages into the QGIS UI.
- Historical QGIS 3.44.13/4.0.0 offscreen UI evidence is not a viewer qualification.
  Clean Windows profile and all-product real-run gates remain independent.

## Milestones

34A1 establishes source identity, source-space selection, session journal and
runtime capability contracts. No new navigation is exposed yet. Existing
Process code and engine dependencies are unchanged.

34A2 must implement and validate the interactive viewer, polygon selection,
overlays, managed export, explicit Process handoff and runtime/package parity.
Only then prepare the requested `0.3.0-beta.1` drop. The current version is
deliberately not bumped for a contract-only intermediate milestone.

See [architecture](POINT_CLOUD_EDITOR_ARCHITECTURE.md) and
[research](../research/PHASE_34A_POINT_CLOUD_EDITOR_ECOSYSTEM_REVIEW.md).
