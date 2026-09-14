# Testing Strategy

Phase 29E adds product/output contract, normalized-error, safe-retention, current-attempt filtering, and 50-cycle current/historical state soak tests. Benchmark analyzers are explicit developer commands and never run during ordinary processing. Live outcomes remain `Not tested live` until executed on the stated platform.

Testing must cover both scientific workflow integrity and QGIS integration.

## Test Layers

- Unit tests for plugin core services.
- Algorithm wiring tests for QGIS Processing parameters and outputs.
- Integration tests against QGIS where feasible.
- Small sample-data tests for reproducible product generation.
- Documentation checks for user-facing workflows.

## Recommended Tools

- `pytest` for Python tests.
- `pytest-qgis` or QGIS test utilities for QGIS integration tests.
- `ruff` for linting and formatting.
- Continuous integration for non-QGIS tests on every pull request.
- Scheduled or release-gated QGIS integration tests.

## Sample Data Policy

Sample data must be small, redistributable, documented, and scientifically
appropriate for tests or tutorials. Large lidar datasets should not be committed
to the repository.

## Acceptance Standards

- New behavior includes tests.
- Algorithm outputs are validated against known fixtures when practical.
- Dependency failure paths are tested.
- Release candidates pass the documented compatibility matrix.

## Performance Evidence

Performance changes require a baseline, a reproducible measurement, and an equivalence check. `scripts/benchmark_adaptive_processing.py` covers synthetic small, medium, large, and very-large planning cases across EPT, COPC, and native-folder assumptions. Synthetic planning measurements must be labeled separately from real LiDAR/QGIS measurements. Scientific equivalence checks must compare grid identity, NoData, valid cells, maximum absolute difference, and RMSE where numeric fixtures are available.

