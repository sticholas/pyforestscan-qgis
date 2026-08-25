# Process Workspace Control State Matrix

| Semantic state | Profile | Execution mode | Workers | Polygon finalization | Repository options | Process inputs |
|---|---|---|---|---|---|---|
| Folder, idle | Always | Custom only | Custom + Parallel | Hidden | Hidden | Enabled |
| Polygon, no repository | Always | Custom only | Custom + Parallel | Available | Hidden | Enabled |
| Polygon, repository selected | Always | Custom only | Custom + Parallel | Available | Available | Enabled |
| Active validation/run/finalization | Visible | Current projection | Current projection | Current projection | Current projection | Disabled |
| Terminal complete/warning/failed/cancelled/interrupted | Visible | Derived from profile | Derived from profile | Derived from mode | Derived from repository | Enabled |

Product settings are visible only when at least one product is selected. Resolution is applicable to raster products; height bins to PAD/PAI/FHD; canopy threshold to Canopy Cover; interpolation to CHM. Collapse state hides only the durable content container and never changes these semantic flags.

Parallel confirmation is never visible. Software guardrails and adaptive resource policy choose effective concurrency. Maximum Workers is an upper bound, not a forced worker count.
