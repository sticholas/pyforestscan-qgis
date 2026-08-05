# Mission Control UX Standard

Mission Control should always answer one question: what is the next thing the user should do?

This standard applies to every future Mission Control page, dialog, panel, and workflow. It is a presentation and information-architecture standard, not a processing standard. The broader plugin visual language lives in the [PyForestScan Design System](PYFORESTSCAN_DESIGN_SYSTEM.md).

## Design Philosophy

- Guide the user through one visible processing path in Batch: choose mode, data, products, output, Prerun Check, Process.
- Show the essential decision first.
- Collapse, hide, or move technical detail to Advanced, Technical Details, or Troubleshooting.
- Use professional GIS terminology and consistent page structure.
- Keep engineering terms such as manifest, registry, bootstrap, runtime, implementation, and internal out of the primary workflow; expose them only under Advanced, Technical Details, or Troubleshooting.
- Preserve the Advanced Toolbox as the parameter-rich expert surface.

## Workflow Model

The visible product workflow starts in Batch and continues to Results. Scientific Advisor is optional guidance; Environment and Settings are readiness/support pages; Advanced Toolbox is the expert surface. Home, Workspace, Dataset, Planning, and Processing remain internal compatibility pages and must not reappear in primary navigation without a separate product decision.

Batch offers LiDAR Folder Selection and Polygon Selection. Normal use follows data, products, output, Prerun Check, and Process. Readiness markers are small text-adjacent markers and never replace status words.

## Interaction Lifecycle

Mission Control actions should behave like one application, not unrelated forms. When an action starts, disable the triggering button and any conflicting action buttons, show a concise running status, and keep technical logs collapsed. When the action completes, refresh dependent pages automatically, restore available controls, and show one clear success, warning, or error message through the QGIS message bar when available. Dataset changes clear downstream plan, processing, advisor, and result state. Backend changes refresh Environment and Home. Processing and batch completion update Results and Home.

Session-aware pages should render from the shared Project Summary rather than duplicating product/load-state logic. Current-session state is in memory only: no recent-project database, autosave, or saved-session behavior should be added under this standard without a separate phase.

## Layout Rules

- Do not show empty sections. If a section has no meaningful content, hide it.
- Use one visually dominant primary action per page.
- Cards size to content and avoid fixed-height empty panels. Small text-only cards should use content-sized labels instead of large text boxes.
- Keep status information in one place per page.
- Minimize scrolling on a 1920 x 1080 display.
- Use whitespace to separate ideas, not to reserve empty panel space.
- Keep button order consistent: primary action first, secondary actions next, advanced/troubleshooting last.

## Empty State Rules

Empty states are compact guidance, not substitute sections.

- Scientific Advisor: `Analyze a dataset to receive recommendations.`
- Results: `No outputs yet. Run processing to generate scientific products.`
- Workspace: `Open or create a workspace to begin.`
- Dataset: `No dataset selected. Select a LAS, LAZ, or COPC dataset to begin.`
- Planning: `Analyze a dataset before choosing products.`

If the user has not reached a workflow step, the page should show the one next action and hide downstream panels.

## Primary Actions

| Page | Primary action |
| --- | --- |
| Home | Continue |
| Workspace | Resume Workspace |
| Dataset | Analyze Dataset |
| Planning | Continue to Processing |
| Processing | Run Processing |
| Batch | Process Folder / Process Selection |
| Results | Load into QGIS / Open Output Folder |
| Scientific Advisor | Review Recommendations |
| Environment | Refresh Environment |
| Settings | Verify Backend |

## Page Structure

| Page | Show first | Collapse or hide |
| --- | --- | --- |
| Home | Backend/environment readiness, selected dataset, workflow status, current output folder, Continue, Check Environment | Version details, recent activity |
| Workspace | Current workspace, last activity, compact timeline summary, recent datasets | History/version detail, reset controls |
| Dataset | Selected dataset, Analyze Dataset action, dataset summary after analysis | Metadata and report paths |
| Planning | Selected products, shared settings, estimated outputs, Continue to Processing | Advanced product settings and parameter explanations |
| Processing | Current job, progress, execution backend, output folder, Run Processing, Next Step to Results after completion | Backend logs, technical output, job JSON |
| Batch | Processing mode, data, products, output folder, Prerun Check, Process | Repository tools, spatial tools, processing profile, footprint, diagnostics |
| Results | Generated products, Load into QGIS, Open Output Folder, processing summary | Logs and diagnostics |
| Scientific Advisor | Executive summary, populated recommendations/products/actionable warnings | Empty recommendation/warning cards, product explanations, scientific notes |
| Environment | Overall status, PBM status, execution backend, Refresh, Backend Settings | QGIS fallback, dependency details, technical checks/logs |
| Settings | Backend, Workspace, General | Manifest registry, module registry, logs, developer-only information |

## Technical Disclosure

Technical content includes Python paths, manifest versions, dependency registries, JSON files, backend internals, log locations, and module registries. It must be hidden by default under a clearly named Advanced, Technical Details, or Troubleshooting section.

## Warning Rules

Warnings appear only when actionable. A warning should state what happened and what the user should do next. Generic caution text belongs in documentation, not in the primary UI.

## Future UI Requirements

- New Mission Control pages must define a primary purpose, one primary action, empty state, and technical disclosure boundary before implementation.
- New buttons must use the same terminology as this standard.
- New diagnostics must not create always-visible walls of technical text.
- New processing capability must not make Guided Mode behave like the Advanced Toolbox.
- External Worker mode remains disabled unless explicitly re-scoped in a future phase.

## Contextual Help

Mission Control uses `InfoHelpButton` for concise help on controls that affect CRS, scientific interpretation, performance, memory, clipping, concurrency, overwrite behavior, or output meaning. Tooltips are short; click details provide 40-120 words when needed.


## Phase 27K Help Standard

Use clear labels before adding help. Add InfoBadge controls only for scientific terms, CRS behavior, backend/runtime behavior, workload uncertainty, performance, memory, output meaning, or risky Advanced/Troubleshooting settings. Keep Guided mode clean and place raw WKT, raw bounds, enum values, and command details under Technical diagnostics.

## Phase 27N Polygon Guidance

Polygon Area Processing uses the guided sequence Data, Area, Outputs, Settings, Review, Results. Advanced settings stay collapsed, and no-intersection states offer spatial preview and extent actions.

## Phase 28A productized workflow

Mission Control opens on **Batch** and shows the primary sidebar **Batch, Results, Scientific Advisor, Environment, Settings, Advanced Toolbox**. Home, Workspace, Dataset, Planning, and Processing remain internal compatibility pages. Normal processing uses **LiDAR Folder Selection** or **Polygon Selection**, then products, output folder, **Prerun Check**, and **Process**. Repository and spatial specialist controls are collapsed under Advanced sections.

## Qt section ownership hotfix

The first Phase 28A build reordered the Products section by removing its owner widget and then calling `parentWidget()` through the old `QVBoxLayout` wrapper. Qt had deleted the underlying C++ layout, so Mission Control failed during `BatchPage` construction. Major Batch sections now have explicit, durable `QGroupBox` attributes and are inserted at creation time. Layout objects are used only to arrange children; they are never moved or queried to rediscover a section after removal.

QGIS 3.44.9 / Python 3.12 offscreen runtime construction and two plugin init/unload cycles pass. Interactive ZIP installation and visual QGIS validation remain pending; the regression checklist records the exact steps and must not be marked passed until run in the GUI.

## Reactive retained pages

Retained pages render typed session/read-model state. Input changes invalidate derived plans immediately; page navigation must not be used as a refresh mechanism.

## Compact retained workflow

Normal Batch order is Processing Mode, LiDAR Data or Processing Area, Products, Output Folder, Prerun Check, Process. Derived reports are summarized normally and expanded only under Technical Report. Empty controls release layout space.

## Runtime status
The footer vocabulary is `Backend`, `LiDAR`, `Area`, and `Status`. Current-run failures show their last known stage and reason; previous runs are not merged into current outputs.
