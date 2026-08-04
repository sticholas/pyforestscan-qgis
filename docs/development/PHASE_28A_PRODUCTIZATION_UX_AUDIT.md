# Phase 28A Productization and Workflow Audit

## Outcome

Mission Control now presents one primary processing workspace instead of exposing its internal guided architecture. Existing Home, Workspace, Dataset, Planning, and Processing pages remain instantiated and connected for compatibility, but are hidden from primary navigation.

## Page hierarchy

The primary sidebar is:

1. Batch
2. Results
3. Scientific Advisor
4. Environment
5. Settings
6. Advanced Toolbox

Batch opens first. Scientific Advisor is optional. Advanced Toolbox opens the existing QGIS Processing Toolbox; it is not a replacement implementation.

## Page audit

| Page | Primary purpose | Phase 28A decision |
| --- | --- | --- |
| Home | Legacy workflow dashboard | Hidden; state and signals preserved internally. |
| Workspace | Session persistence | Hidden; automatic session behavior preserved. |
| Dataset | Single-file exploration | Hidden from primary navigation; internal support preserved. |
| Planning | Product-plan construction | Hidden; product choice is visible in Batch. |
| Processing | Single-run execution detail | Hidden; Batch is the visible processing workspace. |
| Batch | Select data, products, output, validate, process | Becomes the primary workspace and startup page. |
| Results | Review and load generated products | Generated products and Load into QGIS remain first; diagnostics stay collapsed. |
| Scientific Advisor | Optional scientific guidance | Retained as an optional report, never a required step. |
| Environment | Readiness and recovery | Retained with PBM status first and fallback details collapsed. |
| Settings | User defaults and PBM controls | Retained; technical logs remain collapsed. |

## Updated workflow

Normal use follows: choose LiDAR Folder Selection or Polygon Selection, browse data, choose products, choose an output folder, run Prerun Check, then Process. Repository type, setup strategy, CRS alignment, processing profile, worker count, and execution order retain automatic defaults.

## Hidden or moved controls

Primary navigation hides Home, Workspace, Dataset, Planning, and Processing. Advanced Repository Tools contains setup-method overrides, existing-index selection, direct/catalog selection overrides, inspection, header scan, resume/pause, repair, CRS assignment, coverage display, source viewer, diagnostics export, EPT repair, catalog relocation, and catalog-folder access. Advanced Spatial Tools contains selected-file preview, alignment preview, extent zoom actions, rerun, and reset.

All moved controls remain connected to their existing behavior. No placeholder action was retained in the normal workflow.

## Terminology

| Previous | Phase 28A |
| --- | --- |
| Standard File Batch | LiDAR Folder Selection |
| Polygon Area Processing | Polygon Selection |
| Preflight | Prerun Check |
| Run Batch | Process Folder / Process Selection |
| Load Outputs | Load into QGIS |

## Screenspace reduction

The polygon repository row drops three secondary actions, the normal repository area drops specialist strategy and catalog controls, and seven spatial/recovery actions move into collapsed sections. Product choice is placed before output selection, and the readiness report uses a compact content-sized panel. This removes the largest button clusters and technical text blocks from the default view while preserving access one expansion away.

## Preserved boundaries

Scientific algorithms, PBM installation, backend routing, product generation, batch execution, Advanced Toolbox providers, and External Worker policy are unchanged.

## Qt section ownership hotfix

The first Phase 28A build reordered the Products section by removing its owner widget and then calling `parentWidget()` through the old `QVBoxLayout` wrapper. Qt had deleted the underlying C++ layout, so Mission Control failed during `BatchPage` construction. Major Batch sections now have explicit, durable `QGroupBox` attributes and are inserted at creation time. Layout objects are used only to arrange children; they are never moved or queried to rediscover a section after removal.

QGIS 3.44.9 / Python 3.12 offscreen runtime construction and two plugin init/unload cycles pass. Interactive ZIP installation and visual QGIS validation remain pending; the regression checklist records the exact steps and must not be marked passed until run in the GUI.

## Phase 28B follow-up

Retained-page state now flows through `MissionControlSessionState`; Advanced Toolbox has a visible service-backed action and fallback page.

## Phase 28C compaction

The product-focused sidebar is unchanged. Retained pages now use content-driven sizing and state-dependent visibility; the minimum dock width is 620 pixels.
