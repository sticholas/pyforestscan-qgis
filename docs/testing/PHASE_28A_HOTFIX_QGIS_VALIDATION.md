# Phase 28A Hotfix Live QGIS Validation

Target: QGIS 3.44.9 Solothurn, Python 3.12.13, replacement plugin ZIP.

- [ ] Install the replacement ZIP.
- [ ] Enable the plugin with no `initGui()` exception.
- [ ] Confirm Mission Control opens on Batch.
- [ ] Confirm sidebar order: Batch, Results, Scientific Advisor, Environment, Settings, Advanced Toolbox.
- [ ] Switch between LiDAR Folder Selection and Polygon Selection.
- [ ] Expand and collapse Advanced Batch Options, Advanced Repository Tools, and Advanced Spatial Tools.
- [ ] Refresh Environment.
- [ ] Close and reopen Mission Control.
- [ ] Disable and re-enable the plugin.
- [ ] Confirm no deleted-layout or double-delete errors.

Automated runtime evidence: PASS using the installed QGIS 3.44.9 / Python 3.12 runtime with `QT_QPA_PLATFORM=offscreen`. The test constructed and deleted `BatchPage` and `MissionControlDock` twice, verified every named section with `sip.isdeleted()`, verified navigation/default Batch state, and completed two full `PyForestScanPlugin.initGui()` / `unload()` cycles with provider cleanup.

Status: interactive QGIS GUI execution remains pending. The offscreen runtime pass validates Qt ownership and plugin lifecycle, but does not replace visual interaction with the installed ZIP.
