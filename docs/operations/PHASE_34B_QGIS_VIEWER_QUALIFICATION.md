# Phase 34B QGIS Viewer Qualification

Status: NOT YET QUALIFIED

This checklist is evidence capture for a real QGIS session. A passing QGIS-free
test suite does not satisfy these checks. Record QGIS version, Qt version, OS,
source paths, package SHA256, date, and operator before testing.

## Test Matrix

| Area | Result | Notes / evidence |
| --- | --- | --- |
| Small LAS/LAZ opens | [ ] PASS [ ] FAIL | |
| Large LAS/LAZ or COPC opens | [ ] PASS [ ] FAIL | |
| EPT source opens | [ ] PASS [ ] FAIL | |
| RGB mode | [ ] PASS [ ] FAIL [ ] N/A | dimensions and behavior |
| Classification mode and legend | [ ] PASS [ ] FAIL | |
| Elevation / Z mode | [ ] PASS [ ] FAIL | |
| Height Above Ground mode | [ ] PASS [ ] FAIL [ ] N/A | |
| Intensity / other dimensions | [ ] PASS [ ] FAIL [ ] N/A | |
| Overview orbit/pan/zoom | [ ] PASS [ ] FAIL | |
| Area Detail creation and refresh | [ ] PASS [ ] FAIL | |
| Vertical Profile creation | [ ] PASS [ ] FAIL | |
| Multi-segment profile editing | [ ] PASS [ ] FAIL | |
| Profile axes and units | [ ] PASS [ ] FAIL | |
| Height/elevation filtering | [ ] PASS [ ] FAIL | |
| Classification/return filtering | [ ] PASS [ ] FAIL [ ] N/A | |
| Rectangle / polygon / brush selection | [ ] PASS [ ] FAIL | |
| Replace/Add/Subtract semantics | [ ] PASS [ ] FAIL | |
| Source-point selection count | [ ] PASS [ ] FAIL | |
| Measurement workflow | [ ] PASS [ ] FAIL | |
| Tree height / profile measurement | [ ] PASS [ ] FAIL [ ] N/A | |
| DBH workflow | [ ] PASS [ ] FAIL [ ] N/A | not yet implemented is evidence |
| Staged classification + undo/redo | [ ] PASS [ ] FAIL | |
| Detached window interaction | [ ] PASS [ ] FAIL | |
| Detach and redock | [ ] PASS [ ] FAIL | |
| Warm cache switch | [ ] PASS [ ] FAIL | |
| Cold cache switch | [ ] PASS [ ] FAIL | |
| Worker recreation/cache reuse | [ ] PASS [ ] FAIL | |
| Selection to supported product | [ ] PASS [ ] FAIL | |
| Fingerprint replacement rejection | [ ] PASS [ ] FAIL | |
| QGIS project/output integration | [ ] PASS [ ] FAIL | |

## Forestry Scenarios

### A. Forest structure

Open a large cloud, color by HAG, hide upper heights, create a profile, and
inspect the height distribution. Record responsiveness and whether the displayed
sample is clearly distinguished from authoritative counts.

### B. Individual tree

Isolate a tree, inspect its profile, measure height and crown width, and record
whether DBH is available, unavailable, or quality-gated. Do not mark DBH passed
without a visible fit and quality evidence.

### C. Classification QA

Color by classification, select a misclassified region, stage a classification
change, undo, redo, and confirm the original source file hash is unchanged.

### D. Scientific processing

Create an authoritative source-space selection, review the product status, run
preflight, promote the derived plan, execute through PBM, and verify the report
contains the selection identity and source fingerprint.

## Qualification Rule

Do not label the viewer release-ready until every applicable row has evidence,
large-cloud interaction has been observed, and all failures are either fixed or
explicitly accepted as release blockers.
