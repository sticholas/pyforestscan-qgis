# PBM Implementation Plan

## Phase 22A: Foundation

Implemented scope:

- Core backend package.
- Cross-platform user-local path resolution.
- Typed backend models.
- Dependency registry with required and future modules.
- Config serialization helpers.
- Safe state detection and verification.
- Structured log paths and helpers.
- BackendService facade.
- Mission Control Settings status section.
- QGIS-free unit tests.

No installation or backend execution occurs.

## Phase 22B: Installer Design Validation

Recommended next work:

- Choose the micromamba bootstrap source and verification strategy.
- Design package lock/spec files.
- Define exact channels and version pins.
- Add installer dry-run planning output.
- Add manual Windows installer proof outside QGIS.

## Phase 22C: Controlled Installer Prototype

Potential scope:

- Download micromamba to the cache.
- Verify artifact checksums.
- Create user-local backend folder structure.
- Install dependencies into the managed environment.
- Verify backend readiness.
- Preserve rollback/repair records.

## Phase 22D: Backend Execution Bridge

Potential scope:

- Run selected PyForestScan operations through backend Python.
- Define JSON job specs/results for backend execution.
- Keep QGIS responsive and protected from backend crashes.
- Preserve current QGIS Python workflow until backend execution is proven.
