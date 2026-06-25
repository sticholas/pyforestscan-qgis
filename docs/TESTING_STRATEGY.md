# Testing Strategy

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

