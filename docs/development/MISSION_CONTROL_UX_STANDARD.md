# Mission Control UX Standard

Mission Control should always answer one question: what is the next thing the user should do?

This standard applies to every future Mission Control page, dialog, panel, and workflow. It is a presentation and information-architecture standard, not a processing standard. The broader plugin visual language lives in the [PyForestScan Design System](PYFORESTSCAN_DESIGN_SYSTEM.md).

## Design Philosophy

- Guide the user through one clear path: Home, Dataset, Planning, Scientific Advisor, Batch, Results.
- Show the essential decision first.
- Collapse, hide, or move technical detail to Advanced, Technical Details, or Troubleshooting.
- Use professional GIS terminology and consistent page structure.
- Preserve the Advanced Toolbox as the parameter-rich expert surface.

## Workflow Model

Primary workflow pages are Home, Dataset, Planning, Scientific Advisor, Batch, and Results. Environment, Settings, and Workspace are support pages. They remain available from navigation, but the primary UI should make the next workflow step obvious without forcing a wizard.

Primary workflow pages may show a subtle step indicator using completed, current, and upcoming markers. Each primary workflow page should end with one concise Next Step card that names the recommended action and moves to the next page when possible.

## Layout Rules

- Do not show empty sections. If a section has no meaningful content, hide it.
- Use one visually dominant primary action per page.
- Cards size to content and avoid fixed-height empty panels.
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
| Environment | Refresh Environment |
| Dataset | Analyze Dataset |
| Planning | Review Recommendations |
| Scientific Advisor | Open Batch |
| Processing | Run Processing |
| Batch | Run Batch |
| Results | Open Output Folder |
| Settings | Verify Backend |

## Page Structure

| Page | Show first | Collapse or hide |
| --- | --- | --- |
| Home | Backend status, selected dataset, workflow status, current output folder, Continue | Version details, recent activity |
| Workspace | Current workspace, last activity, compact timeline summary, recent datasets | History/version detail, reset controls |
| Environment | Overall status, PBM status, execution backend, Refresh, Backend Settings | QGIS fallback, dependency details, technical checks/logs |
| Dataset | Selected dataset, Analyze Dataset action, dataset summary after analysis | Metadata and report paths |
| Scientific Advisor | Executive summary, populated recommendations/products/actionable warnings, Next Step to Batch | Empty recommendation/warning cards, product explanations, scientific notes |
| Planning | Selected products, shared settings, estimated outputs | Advanced product settings and parameter explanations |
| Processing | Current job, progress, execution backend, output folder, Run Processing | Backend logs, technical output, job JSON |
| Batch | Discover Files, Preflight, Run Batch, Review Results | Advanced options, footprint estimate, parallel diagnostics |
| Results | Generated outputs, Open Output Folder, Load Outputs, or compact guidance back to Batch | Technical logs and processing metadata |
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
