# Plugin Roadmap

## Phase 0: Foundation

Purpose: Establish governance, architecture, repository structure, and planning.

Deliverables:

- Repository documentation.
- Directory layout.
- Initial ADRs.
- Roadmap and strategy documents.

Risks:

- Premature implementation before architecture is stable.
- Unclear dependency policy.

Acceptance Criteria:

- New contributors can understand the project direction without reading code.
- Every directory has a documented purpose.

## Phase 1: Plugin Scaffold

Purpose: Create a minimal installable QGIS plugin with no scientific algorithms.

Deliverables:

- QGIS metadata.
- Plugin entry points.
- Processing provider shell.
- Basic plugin loading tests.

Risks:

- QGIS version compatibility issues.
- Incorrect plugin packaging layout.

Acceptance Criteria:

- Plugin loads in supported QGIS versions.
- Processing provider appears with placeholder-free registration.

## Phase 2: Environment Validation

Purpose: Detect whether the QGIS Python environment can use PyForestScan safely.

Deliverables:

- Dependency inspection utilities.
- User-facing diagnostics.
- Documentation for installation paths.

Risks:

- QGIS Python isolation varies by operating system.
- Binary geospatial dependencies may be difficult to install.

Acceptance Criteria:

- Users receive clear, actionable dependency status messages.
- No algorithm starts when required dependencies are unavailable.

## Phase 3: CHM

Purpose: Deliver the first PyForestScan-backed Processing algorithm.

Deliverables:

- CHM Processing algorithm.
- Input validation.
- Output raster metadata.
- Tests with small sample data.

Risks:

- Large lidar files may exceed memory expectations.
- Coordinate reference system assumptions may be unclear.

Acceptance Criteria:

- CHM output is reproducible for documented test data.
- Algorithm can run from Processing Toolbox and Model Builder.

## Phase 4: Forest Metrics

Purpose: Add PAI, PAD, FHD, canopy cover, rumple index, and structural complexity
products.

Deliverables:

- Metric algorithms or grouped workflows.
- Output product documentation.
- Validation for metric-specific parameters.

Risks:

- Metrics may require different input assumptions.
- Users may need stronger guidance on interpretation.

Acceptance Criteria:

- Each metric has documented inputs, outputs, assumptions, and tests.

## Phase 5: Batch Processing

Purpose: Support repeated processing across lidar tiles or directories.

Deliverables:

- Batch-safe parameter handling.
- Naming templates.
- Progress reporting.
- Failure summaries.

Risks:

- Partial failures can be hard to diagnose.
- Long-running workflows need robust cancellation behavior.

Acceptance Criteria:

- Batch runs produce predictable output names and summary logs.
- Failed items do not hide successful results.

## Phase 6: Visualization

Purpose: Provide useful QGIS styles and publication-oriented defaults.

Deliverables:

- QML styles for common rasters and vectors.
- Layer naming conventions.
- Documentation for map-ready outputs.

Risks:

- Styles may imply scientific thresholds that are context-dependent.

Acceptance Criteria:

- Outputs load with appropriate default styling when possible.
- Style files are documented and versioned.

## Phase 7: Automation

Purpose: Improve reproducibility through Model Builder and scripted Processing.

Deliverables:

- Model Builder compatibility review.
- Processing examples.
- Metadata capture for automated workflows.

Risks:

- Hidden state in QGIS projects can reduce reproducibility.

Acceptance Criteria:

- Core workflows can be run from QGIS Processing history or Python console.

## Phase 8: Advanced Workflows

Purpose: Add polygon summaries, advanced metrics, and publication workflows.

Deliverables:

- Polygon summary algorithms.
- Report-ready table outputs.
- Advanced workflow documentation.

Risks:

- Scientific interpretation requirements become domain-specific.
- Performance requirements increase.

Acceptance Criteria:

- Advanced workflows remain modular and documented.
- Outputs include provenance suitable for publication methods sections.

