# Phase 32B UI Startup Matrix

Test artifact: packaged `pyforestscan_qgis.zip` extracted into an isolated profile-style directory.

| Scenario | Expected | QGIS 3.44.13 result |
|---|---|---|
| Engine Ready | Dock opens; processing available | Pass |
| Engine missing / Setup Required | Dock opens; Set Up shown; processing disabled | Pass |
| Engine Repair Required | Dock opens; Repair shown; processing disabled | Pass |
| Engine status Failed | Dock opens; diagnostics/recheck remain available | Pass |
| Stale/incompatible state projection | Dock opens; setup/update guidance shown | Covered by failed-state contract |
| Network unavailable at open | No network operation during construction | Pass by startup isolation guard |
| Exact `_update_status_bar()` regression | No removed-widget access | Pass |
| Open/destroy | 100 cycles | Pass |
| Process / Tools & Setup navigation with state changes | 100 cycles | Pass |
| Widths 420/500/620/800 px | Construct without horizontal expansion | Pass |

QGIS 3.44.9 is installed on the test host without a usable Python-QGIS launcher. Runtime execution used QGIS 3.44.13 LTR; the implementation uses Qt/QGIS APIs already supported by the 3.44 line.
