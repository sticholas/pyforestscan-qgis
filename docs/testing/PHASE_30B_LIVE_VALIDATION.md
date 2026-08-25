# Phase 30B Live Validation

| Scenario | Status | Evidence |
|---|---|---|
| Existing 130 ha Rumple output inspection | PASSED LIVE | TIFF, CSV, PBM result, mask and registry inspected |
| False EPSG:6635 warning removal | NOT TESTED LIVE | Semantic comparison covered by automated test |
| Repeat 130 ha Rumple after Phase 30B | NOT TESTED LIVE | Requires QGIS |
| Immediate second polygon job | NOT TESTED LIVE | Requires QGIS |
| CHM plus Rumple shared execution | NOT TESTED LIVE | Coordinator integration and unit tests only |
| Irregular polygon and holes | NOT TESTED LIVE | Requires real source |
| Coverage gap NoData | NOT TESTED LIVE | Requires real source |
| Medium/large adaptive Rumple | NOT TESTED LIVE | Requires PBM and real source |
| Forced secondary CSV failure | NOT TESTED LIVE | Policy automated; UI requires QGIS |
| Forced QGIS auto-load failure | NOT TESTED LIVE | Policy automated; UI requires QGIS |

No blocked or unavailable live test is reported as passed.
