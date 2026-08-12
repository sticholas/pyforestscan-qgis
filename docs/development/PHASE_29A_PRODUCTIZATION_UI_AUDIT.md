# Phase 29A Productization UI Audit

## Scope

Phase 29A audits the retained **Process** and **Tools & Setup** workspaces as a production desktop interface. Scientific algorithms, PBM installation, backend routing, Processing Toolbox behavior, and external-worker policy are unchanged.

## Layout findings and changes

| Surface | Before | Phase 29A |
|---|---|---|
| Global shell | 112 px navigation, generous card padding, hidden footer | 112 px no-scroll navigation, tighter tokens, and a live responsive current-session strip |
| LiDAR folder | Empty list reserved processing space | One-line empty state; populated list grows through six 72 px rows, then scrolls internally |
| Polygon repository | Maintenance group appeared before a repository was selected | Repository Tools appears only after a polygon repository path exists |
| Products | Every advanced parameter appeared regardless of selection | Advanced settings hide when no product is selected; individual rows follow selected products |
| Execution | Sequential displayed an irrelevant worker count | Max Workers and parallel confirmation appear only for Parallel |
| Readiness | Concise status plus a separately collapsed report | The report is always present, one line when concise, and capped at six lines with internal scrolling |
| Results | Current result behavior was already state-driven | Current result remains hidden until complete current-job outputs exist; result lists are content-capped |
| Tools | Three normal System actions competed equally | Verify Environment remains normal; Toolbox and Guidance move to Additional Tools |
| Preferences | Folder selection required a second Use This Folder action | Editing completion applies the selected folder and a compact preview explains the behavior |
| Backend | Seven summary rows and two action rows occupied the normal page | Four readiness rows and primary actions remain; release detail and secondary actions move under Advanced/Troubleshooting |

## Button audit

| Control family | Owner | Decision | Rationale |
|---|---|---|---|
| Browse, Discover Files | Folder source | Keep | Required source selection and explicit discovery |
| Select All, Clear | Folder source | Keep | Efficient selection of discovered datasets |
| Repository build/update/repair/diagnostic actions | Repository Tools | Hide until repository exists | Capabilities remain available but are irrelevant before source selection |
| Product recommendation/clear | Products | Keep | Compact bulk product decisions |
| Run Detailed Check | Readiness | Keep | Owns deterministic prerun validation |
| Process LiDAR | Process | Keep as primary | One primary execution action |
| Pause, Cancel, Retry | Active processing | State-dependent | Only appear when meaningful |
| Load into QGIS, Open Folder, New Run | Current Result | State-dependent | Only complete current-job output owns these actions |
| Verify Environment | System | Keep | Primary setup diagnostic |
| Open Processing Toolbox, Guidance Details | Additional Tools | Move | Useful but not part of normal processing setup |
| Use This Folder | Preferences | Remove | Editing completion applies the value; duplicate confirmation was unnecessary |
| Verify/Install/Repair Backend | Managed Backend | Keep | Primary backend lifecycle actions |
| Preview plan, compatibility, manual setup, folder, logs, advanced | Backend troubleshooting | Move | Preserved one expansion away from normal readiness |

No scientific or backend action was deleted. One duplicate preference confirmation button was removed; all other controls were retained, moved, or made state-dependent.

## Adaptive behavior contract

- Widths below 620 px show only backend and overall status in the live strip; wider layouts add source and area.
- Empty file lists use a one-line state. Populated lists show at most six rows before internal scrolling.
- Readiness reports resize from one through six visible lines.
- Repository Tools require Polygon mode and a repository path.
- Product settings require selected products. Height bins follow PAD/PAI/FHD, canopy threshold follows Canopy Cover, and interpolation follows CHM.
- Sequential hides Max Workers and parallel confirmation. Parallel reveals both while preserving existing guardrails.
- Current results and result actions remain absent until the active job has final outputs.

## Validation boundaries

QGIS 3.44.9 offscreen construction passed twice at 420, 500, 620, and 800 px. Adaptive form rows, two-workspace navigation, and repeated Qt teardown passed. Offscreen execution is structural evidence, not proof of interactive visual quality, map action behavior, high-DPI themes, or scientific processing.

## Phase 29B opportunities

- Complete the repository button merge/removal review with live action evidence.
- Make polygon spatial actions available directly from valid input state where safe.
- Remove or replace the redundant polygon combined-extent and rerun controls after live verification.
- Decide whether processing profiles should remain user-facing or become fully automatic.
- Correct plugin startup so Mission Control opens only from the user action.
- Validate custom profile controls and safe concurrency limits on representative machines.
