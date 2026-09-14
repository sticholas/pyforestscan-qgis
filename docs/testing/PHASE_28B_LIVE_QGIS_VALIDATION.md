# Phase 28B Live QGIS Validation

## Automated runtime status

QGIS-free unit and package validation are recorded by the Phase 28B commit. Offscreen QGIS construction checks are run where the QGIS 3.44.9 runtime is available.

## Interactive matrix

| Check | Status | Evidence needed |
|---|---|---|
| Install updated ZIP | Not tested live | clean QGIS profile |
| Select first polygon; Advisor reflects it | Not tested live | screenshot with area/source |
| Select another polygon; Advisor updates | Not tested live | before/after signatures |
| Clear polygon; old area disappears | Not tested live | compact no-polygon summary |
| Advanced Toolbox opens/focuses | Not tested live | QGIS panel visible |
| PyForestScan provider visible | Not tested live | expanded/search result |
| Refresh Tools avoids duplicate provider | Not tested live | one provider, algorithm count |
| Run harmless diagnostic algorithm | Not tested live | algorithm result |
| Visit all six sidebar items | Not tested live | no blank/inert page |
| Close/reopen Mission Control | Not tested live | retained current state |
| Disable/re-enable plugin | Not tested live | clean load/unload |

Interactive success must not be inferred from offscreen tests. Complete this matrix on QGIS 3.44.9 before release-candidate sign-off.
