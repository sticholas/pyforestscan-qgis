# Contributing

Thank you for considering a contribution to PyForestScan QGIS. The project is building a production-quality scientific QGIS interface for PyForestScan, so contributions should preserve scientific integrity, maintainability, reproducibility, and clear user workflows.

## Start Here

Before opening a pull request, read:

- [Project Vision](docs/PROJECT_VISION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Documentation Index](docs/README.md)
- [Testing Strategy](docs/TESTING_STRATEGY.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [Architecture Decision Records](docs/adr/README.md)

## Architecture Expectations

Follow the established boundaries:

- Mission Control UI and Processing algorithms must not call PyForestScan directly.
- Guided processing should flow through `JobManager -> Pipeline -> Adapter -> PyForestScan`.
- Expert Processing algorithms should use request builders and adapter methods.
- Core services should remain QGIS-free unless an integration boundary explicitly requires QGIS.
- Scientific thresholds and recommendations must be transparent, configurable where uncertain, and documented.
- External worker execution must remain disabled until a validated headless launcher exists.

## Development Workflow

1. Work from a feature branch based on `develop`.
2. Keep changes cohesive and product-oriented.
3. Add or update tests for behavior changes.
4. Update user, scientific, architecture, or developer docs when behavior changes.
5. Run the relevant validation commands before opening a PR.
6. Include manual QGIS validation notes for UI, Processing Toolbox, packaging, and product-output changes.

Recommended validation:

```bash
python3 -m unittest discover tests
python3 -m compileall pyforestscan_qgis
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
python3 scripts/check_docs_links.py
```

Also run `git diff --check` before committing.

## Scientific Changes

For scientific processing changes, document:

- The exact PyForestScan API used.
- Product-specific parameters and defaults.
- Output format and QGIS display behavior.
- Known limitations and data-quality assumptions.
- Manual QA observations, including CRS, extent, value range, and visual reasonableness.

Do not invent hidden scientific rules. If a threshold is uncertain, document its rationale, make it configurable where appropriate, and mark future calibration needs clearly.

## Documentation Standards

Use stable product language instead of phase-only language in release-facing docs. Historical phase notes belong in [docs/archive/phase-history](docs/archive/phase-history/README.md). Link to current guides from [docs/README.md](docs/README.md).

## Code of Conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
