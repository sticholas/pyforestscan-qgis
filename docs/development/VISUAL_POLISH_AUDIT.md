# Visual Polish Audit

Phase 24F applied the PyForestScan Design System directly to Mission Control without changing processing, PBM installer behavior, scientific calculations, Advanced Toolbox behavior, or product coverage.

## Applied Changes

| Area | Result |
| --- | --- |
| Spacing | Mission Control page margins, section margins, section spacing, action-row spacing, compact list heights, and technical text heights now use design-system token constants in `pyforestscan_qgis/ui/pages.py`. |
| Status badges | Environment, Processing, Batch, and Backend status labels use approved badge wording and tone metadata: READY, RUNNING, WARNING, FAILED, NOT CONFIGURED, DISABLED, or PLANNED. |
| Button hierarchy | Primary, secondary, neutral, and danger button roles are applied to key Mission Control actions and styled from the Mission Control stylesheet. |
| Cards and sections | Section padding is consistent, Advisor cards use shared spacing, and technical details stay collapsed by default. |
| Backend page | Normal controls are split into primary install/verify/repair actions and secondary troubleshooting actions so the page reads calmer during installation. |
| Processing page | Execution backend, status, selected products, output folder, primary Run Processing action, progress, and technical details remain visually distinct. |
| Batch page | The visible workflow remains Discover Files, Preflight, Run Batch, with advanced options and footprint estimate collapsed. |
| Results page | Generated outputs and output-folder actions remain first; job history and run files/logs stay secondary or collapsed. |

## Page Audit

| Page | Phase 24F audit result | Remaining guidance |
| --- | --- | --- |
| Home | Primary Open Dataset action is visually dominant; Batch and Continue are secondary. | Keep Home a dashboard, not documentation. |
| Workspace | Resume Workspace is primary; reset/remove actions are danger role; empty sections remain hidden. | Keep history and reset secondary to resume/start work. |
| Environment | Status badge now uses design-system wording and tone; fallback and technical sections remain collapsed. | Keep QGIS Python details optional when PBM is READY. |
| Dataset | Analyze Dataset is primary; footprint actions are secondary; empty summary/preview sections stay hidden. | Keep report paths out of the primary view. |
| Scientific Advisor | Cards use consistent spacing and compact list sizing. | Keep explanations and scientific notes collapsed. |
| Planning | Build Plan is primary; product selection and shared settings stay visible; advanced product settings remain collapsed. | Avoid turning Guided Mode into the Advanced Toolbox. |
| Processing | Execution backend and status badge are prominent; logs and JSON overrides remain in Technical Details. | Keep PBM/QGIS fallback wording explicit. |
| Batch | Discover, Preflight, and Run use the primary action style inside the three-step flow. | Keep Parallel Safe secondary and External Worker disabled. |
| Results | Generated outputs are first; Open Output Folder is the primary result action; Clear Current Run is danger. | Keep raw reports/logs collapsed. |
| Settings / Backend | Backend status badge, staged progress, and split action rows make the installer page calmer. | Keep install details and logs under Advanced/Troubleshooting. |

## Verification Notes

The design-system vocabulary remains QGIS-free in `pyforestscan_qgis/ui/ux_summary.py`. Static tests assert token use, role metadata, status badge wording, compact empty states, and collapsed technical sections.
