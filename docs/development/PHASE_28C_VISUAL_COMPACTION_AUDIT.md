# Phase 28C Visual Compaction Audit

## Scope and method

The retained interface was audited structurally and in QGIS 3.44.9 offscreen at 620, 980, and 1400 pixel widths with 100% and 150% scale factors. Interactive Windows theme and map-action results are tracked separately because offscreen construction is not live visual validation.

## Page findings and changes

| Page | Finding | Change |
|---|---|---|
| Batch | Technical preflight, footprint estimate, result controls, and maintenance actions competed with the normal flow | Normal hierarchy is Processing Mode, LiDAR Data/Processing Area, Products, Output Folder, Prerun Check, Process. Repository, spatial, product settings, batch options, and technical report are collapsed. Result controls appear only after results exist. |
| Results | Empty state retained disabled output controls and multiple status categories | Empty state is one sentence plus Go to Batch. Output actions and compact generated/loaded status appear only with outputs. Diagnostics remain collapsed. |
| Scientific Advisor | State signature appeared as normal content | Normal context now says guidance reflects current Batch selections. Empty recommendation sections remain hidden; detailed explanations remain collapsed. |
| Environment | Technical lists could grow inside expanded sections | Normal readiness remains concise. Fallback and dependency lists are collapsed and height-bounded. |
| Settings | Workspace persistence and backend report content occupied normal preference space | Common output default remains first. Workspace options are Advanced Settings; backend report content remains under Advanced/Troubleshooting and is height-bounded. |
| Advanced Toolbox | Compact fallback lacked documentation action | Added View Tool Documentation beside Open Processing Toolbox and Refresh Tools. No algorithm list is duplicated. |

## Batch workflow

Before compaction, the normal Batch surface exposed seven main sections plus footprint/report/list areas and several equally prominent recovery controls. After compaction, seven purpose-named sections remain, but irrelevant mode sections, internal result controls, technical reports, and specialist tools collapse or disappear by state.

Folder path requires approximately: mode decision, folder browse, discovery, product confirmation, output browse, Prerun Check, Process. Polygon path adds repository setup and polygon source selection. Recommended CHM is selected by default; Select Recommended and Clear Selection reduce product decisions.

## Action hierarchy

- Primary: Discover/prepare as needed, Run Prerun Check, Process, Load into QGIS, Open Processing Toolbox.
- Secondary: Select Recommended, map preview, refresh, open folder.
- Advanced: repository maintenance, spatial alignment/coverage tools, worker controls, output conflict policy, polygon finalization, diagnostics.
- Hidden until relevant: resume, result filters/list, output controls in an empty Results page, vector sublayer selector, repair-only repository actions.

## Terminology

Normal labels now use LiDAR Data, Processing Area, Products, Output Folder, Prerun Check, Process, Repository Tools, Map and Spatial Tools, and Technical Report. Raw WKT is labeled Technical WKT and remains hidden. Catalog, mask-engine, worker, and execution details stay in advanced sections.

## Content sizing and accessibility

Mission Control's minimum size changed from 1150 x 760 to 620 x 520. Full-page scrolling remains; nested section scrolling was not added. Technical lists and text reports use maximum heights rather than large normal minimums. Status remains textual, controls retain keyboard-native Qt behavior, mode selection has an accessible name and tooltip, labels wrap, and QGIS theme icons retain Qt fallbacks.

## Remaining visual limitations

Interactive light/dark theme review, actual Windows 100%/150% display review, keyboard traversal, and map/canvas side effects require the live checklist. Offscreen screenshots are useful for construction and geometry only; their font rendering is not release evidence.
