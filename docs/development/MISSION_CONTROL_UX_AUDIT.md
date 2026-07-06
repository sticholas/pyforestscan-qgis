# Mission Control UX Audit

Phase 24B reviewed Mission Control for internal beta continuity. The intended path is:

1. Check backend.
2. Select dataset or batch folder.
3. Review recommendation.
4. Choose products.
5. Run.
6. Review outputs.

## Page Audit

| Page | Primary purpose | Primary action | Phase 24B simplification |
| --- | --- | --- | --- |
| Home | Compact workflow dashboard. | Start Single Dataset, Start Batch, Continue Last Run. | Reduced to backend status, environment status, current dataset/batch, last output folder, and primary actions. Recent activity and version details stay collapsed. |
| Environment | Answer whether processing can run. | Refresh, Open Backend Settings. | PBM status and active execution backend are visible first; QGIS Python fallback checks and technical dependency details are collapsed by default. |
| Dataset | Select one lidar dataset and run Dataset Explorer. | Run Dataset Explorer. | Kept focused on dataset path, output folder, summary, and footprint preview. |
| Scientific Advisor | Turn Dataset Explorer output into practical next steps. | Read executive summary, then continue to Planning. | Executive summary remains first; product explanations, tool instructions, and scientific notes stay collapsed. |
| Planning | Choose products and shared defaults. | Build Plan. | Product selection and shared settings remain primary; advanced product settings stay collapsed. |
| Processing | Run the active Product Plan. | Run Selected Products. | Adds explicit execution backend line; technical plan/log controls remain collapsed. |
| Results | Review generated outputs. | Open Output Folder, Load Outputs, Clear Current Run. | Generated outputs appear first; internal reports and logs remain collapsed. |
| Batch | Run the same products for many files. | Discover Files, Preflight, Run Batch. | Reframed as a three-step workflow; parallel and retry tuning moved under Advanced Batch Options; footprint estimate is collapsed. |
| Settings / Backend | Manage PBM safely. | Verify Backend or Install Backend. | Normal beta path is short; install plans, logs, module registry, and repair detail remain under advanced/troubleshooting actions. |
| Workspace | Resume local work context. | Continue Last Workspace or Start New Workspace. | Left intact for recovery/resume, while Home exposes only Continue Last Run. |

## Guidance

- Keep Guided Mode simple and path-oriented.
- Keep Advanced Toolbox parameter-rich and unchanged.
- Keep PBM installer behavior unchanged.
- Keep External Worker mode disabled.
- Add new technical detail only behind collapsed Advanced or Troubleshooting sections.
