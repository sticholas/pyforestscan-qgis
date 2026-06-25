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

## Phase 5A: Dataset Explorer

Purpose: Provide the first complete guided inspection workflow before CHM implementation.

Deliverables:

- Adapter-backed dataset validation and inspection.
- JSON, CSV, and HTML planning reports.
- Product feasibility and warnings.

Risks:

- Large LAS/LAZ/COPC inspection may require future sampling controls.
- EPT classification summaries are metadata-limited.

Acceptance Criteria:

- No scientific products generated.
- Reports document dataset readiness and warnings.
- CSV summary can be loaded as a QGIS table.

## Phase 6: Product Planner

Purpose: Help users choose future PyForestScan products from a Dataset Explorer
report before any scientific processing is implemented.

Deliverables:

- Product Planner Processing algorithm.
- JSON, CSV, and HTML product plan reports.
- Requested product validation against Dataset Explorer feasibility.
- Estimated future output paths, grid size, and height-bin count.

Risks:

- Planned output names may need refinement when real product writers are added.
- Feasibility depends on Dataset Explorer metadata and may need stronger checks
  once CHM processing begins.

Acceptance Criteria:

- No PyForestScan calculations are run.
- No rasters or scientific products are created.
- Product plan reports document readiness, warnings, and next actions.

## Phase 7A: Mission Control Framework

Purpose: Establish the official dockable operating environment for current
PyForestScan QGIS workflows.

Deliverables:

- Mission Control dock and toolbar/menu action.
- Modular Home, Environment, Dataset, Planning, Processing, Results, and Settings
  pages.
- In-memory orchestration of Environment Check, Dataset Explorer, and Product
  Planner summaries.

Risks:

- QGIS UI behavior requires manual desktop validation.
- Future scientific processing will need stronger async/progress handling.

Acceptance Criteria:

- Dock opens and navigation works.
- Current workflows remain available from Processing Toolbox.
- No scientific processing is implemented.
