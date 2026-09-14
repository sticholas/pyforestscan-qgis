# Phase 32V Compact Density Audit

## Scope

Phase 32V preserves the Phase 32U workflow order and all scientific, Processing Engine, repository, checkpoint, and output contracts. It changes Qt sizing and adds a direct action for adopting features already selected with standard QGIS map tools.

## Excess-height sources and repairs

| Widget or layout | Previous behavior | Actual requirement | Repair |
| --- | --- | --- | --- |
| `MissionPage.content_widget` | `MinimumExpanding` invited the scroll widget to distribute spare height through configuration content. | Width expansion and content-derived height. | Use vertical `Preferred`; remaining Process workspace height is consumed by one bottom stretch. |
| Page and section layouts | Medium/large spacing and 8 px section margins accumulated at every row. | 4 px row/heading spacing, 8 px section separation. | Page margins use `sm/xs`; section margins and row spacing use `xs`; major gaps use `sm`. |
| Routine Process `QGroupBox` widgets | Vertical `Minimum` could accept extra height; title-margin reduction caused title/control overlap during the first iteration. | Current layout size only, with an independent small heading. | Use vertical `Maximum`, clear group titles, and insert content-sized `compactSectionHeading` labels. |
| Process workspace | No terminal stretch, so spare height could be assigned among sections. | Spare space after configuration. | Add one stretch after the final Processing section; no stretch exists between configuration sections. |
| Products | Parent policy and accumulated margins produced a 125 px region for two checkbox rows and collapsed Advanced. | Heading, two natural checkbox rows at wide width, and one collapsed row. | Content-sized parent, 4-column/2-column responsive grid, zero row stretch, hidden product actions. |
| Advanced Scientific Settings | Collapsed group retained group margins and a non-zero body sizing policy. | Approximately one title row while collapsed; visible relevant rows while expanded. | Body gets maximum height zero while hidden, vertical `Maximum` while visible, layout invalidation on visibility changes, and reflow only when expanded. |
| Output | A titled group plus generous margins produced a 125 px block. | One label/path/Browse row at normal width. | Clear the group title and insert `Output` into the path row. No normal-state status row exists. |
| Prerun/Process actions | Process retained a 220 px maximum while Prerun consumed remaining width. | Equal width and equal natural height. | Remove the maximum, use equal grid-column stretch, and apply one shared computed height. |
| Area utility buttons | Horizontal `Ignored` policy allowed Refresh and Zoom to collapse to zero width. | Natural command width. | Use horizontal `Fixed`; Refresh, Use Selected Features, and Zoom remain together. |
| Context help | Maximum 54 px reserved more than its ordinary one-line state. | One line normally, bounded wrapping when needed. | Reduce maximum to 42 px; measured normal height is 23 px. |
| Collapsible sections globally | Hidden bodies were invisible but retained permissive maximum geometry and padded outer layout. | One compact title row when closed. | Apply zero hidden-body maximum height, 4 px margins, vertical `Maximum`, invalidate parent geometry. |

## QGIS 3.44.13 measurements

The same installed-package harness used a 1400x900 floating Mission Control window and a 1274x753 Process viewport. The Phase 32U package was measured before replacement; Phase 32V was measured after clean ZIP installation.

| Section | Phase 32U | Phase 32V | Change |
| --- | ---: | ---: | ---: |
| Mode | 125 px | 38 px | -87 px |
| LiDAR (hidden in Polygon mode) | 155 px | 146 px | -9 px |
| Processing Area | 305 px | 278 px before duplicate-summary removal | -27 px |
| Products, including collapsed Advanced | 125 px | 90 px | -35 px |
| Advanced collapsed alone | 53 px | 19 px | -34 px |
| Output | 125 px | 36 px | -89 px |
| Action height | 36 px | 24 px | -12 px |
| Context help | 23 px | 23 px | unchanged natural height |
| Configuration total | 716 px | 466 px | -250 px / 34.9% |

The final removal of the duplicate selected-layer message further reduces Processing Area by one natural text row. Configuration containers have no unexplained internal blank rectangles; deliberate separation remains between workflow sections, and spare viewport height appears after content.

## Products and Advanced

At a 1274 px viewport, eight products occupy four columns and two rows. Below 720 px they occupy two columns and four rows. Product controls remain fixed-height and the grid has no vertical stretch.

Collapsed Advanced is 19 px in real QGIS. Its hidden body has maximum height zero. Product toggles update contextual row visibility without resizing the closed group. When open, adding FHD exposes only FHD-related rows and removing it invalidates the layout immediately so the panel returns to the CHM-only height.

## Selected features from QGIS

Polygon mode retains the existing `selected` versus `full` layer contract. **Use Selected Features** refreshes the chosen QGIS layer, adopts its current selected feature IDs, invalidates stale readiness, and republishes the normal session state. Prerun later calls the same `normalize_qgis_layer_selection` function and automatic dissolve policy used before Phase 32V; there is no alternate geometry or science path.

The live QA memory layer used EPSG:32605 polygons. One selected feature normalized to 10,000 m2 and five selected features normalized to 50,000 m2. Clearing selection disabled the action; reselecting restored it. Refresh and Zoom to Area completed without exception. Selection adoption does not run Prerun, inspect EPT, prepare a repository, or launch the Processing Engine.

## Visual gate

Real QGIS 3.44.13 screenshots at 1400x900 verify the installed before and after packages. The first Phase 32V iteration was rejected because compact group-title margins caused overlap and horizontal `Ignored` policies hid Refresh/Zoom. Explicit headings and natural-width utility controls corrected both defects before signoff.

Final release QA must repeat the deterministic CHM canary and installed/source/ZIP parity checks after the clean-tree package rebuild.
