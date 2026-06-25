# Dependency Strategy

The plugin must treat PyForestScan as an external computational dependency, not
as vendored code.

## Principles

- Do not vendor PyForestScan into the plugin repository.
- Depend only on public PyForestScan APIs.
- Isolate PyForestScan calls behind plugin-owned adapter boundaries.
- Document dependency expectations separately from plugin code.
- Do not install dependencies automatically without explicit user action.

## Expected Runtime Dependencies

The eventual plugin is expected to need:

- QGIS and its Python environment.
- PyQt and QGIS Python APIs provided by QGIS.
- PyForestScan.
- PyForestScan transitive scientific and geospatial dependencies.

Specific version ranges must be confirmed during implementation and release
testing.

## Optional Dependencies

Optional dependencies may support advanced exports, reports, visualization, or
performance. Optional dependencies must not prevent basic plugin loading.

## Environment Validation

The plugin should include a diagnostic workflow that reports:

- QGIS version.
- Python version used by QGIS.
- PyForestScan availability and version.
- Required geospatial dependency availability.
- Known compatibility warnings.

## Packaging Position

The QGIS Plugin Repository package should remain lightweight. Scientific Python
dependencies should be handled through documented installation strategies for
the user's platform and QGIS distribution.

