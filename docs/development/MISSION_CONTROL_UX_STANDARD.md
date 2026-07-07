# Mission Control UX Standard

Mission Control should always answer one question: what is the next thing the user should do?

This standard applies to every future Mission Control page, dialog, panel, and workflow. It is a presentation and information-architecture standard, not a processing standard. The broader plugin visual language lives in the [PyForestScan Design System](PYFORESTSCAN_DESIGN_SYSTEM.md).

## Design Philosophy

- Guide the user through one clear single-dataset path: Home, Workspace if needed, Dataset, Planning, Processing, Results.
- Show the essential decision first.
- Collapse, hide, or move technical detail to Advanced, Technical Details, or Troubleshooting.
- Use professional GIS terminology and consistent page structure.
- Keep engineering terms such as manifest, registry, bootstrap, runtime, implementation, and internal out of the primary workflow; expose them only under Advanced, Technical Details, or Troubleshooting.
- Preserve the Advanced Toolbox as the parameter-rich expert surface.

## Workflow Model

Primary single-dataset workflow pages are Home, Workspace when needed, Dataset, Planning, Processing, and Results. Batch is optional and must not be part of the default Continue path. Scientific Advisor is supporting guidance and must not be forced before Processing. Environment and Settings are readiness/support pages. They remain available from navigation, but the primary UI should make the next workflow step obvious without forcing a wizard.

Primary workflow pages may show a subtle step indicator using completed, current, and upcoming markers. Batch may show its own controls when users explicitly choose Batch, but it should be omitted from the default single-dataset indicator. Readiness markers are small text-adjacent markers and never replace status words.

## Interaction Lifecycle

Mission Control actions should behave like one application, not unrelated forms. When an action starts, disable the triggering button and any conflicting action buttons, show a concise running status, and keep technical logs collapsed. When the action completes, refresh dependent pages automatically, restore available controls, and show one clear success, warning, or error message through the QGIS message bar when available. Dataset changes clear downstream plan, processing, advisor, and result state. Backend changes refresh Environment and Home. Processing and batch completion update Results and Home.

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
| Batch | Run Batch |
| Results | Open Output Folder |
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
| Batch | Discover Files, Preflight, Run Batch, Review Results | Advanced options, footprint estimate, parallel diagnostics |
| Results | Generated outputs, Open Output Folder, Load Outputs into QGIS, or compact guidance back to Processing | Technical logs and processing metadata |
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
