# Phase 34A4 Large-Source Evidence

## Scope

Qualification against code commit f9e8f86 on Windows 11, QGIS 3.44.13.
These are automated native-renderer and managed-runtime checks, not human
mouse acceptance or a sustained performance benchmark. No default QGIS
profile was deployed and no original point cloud was modified.

Artifacts are under
`C:/Users/Milo/Documents/PyForestScan-QGIS/artifacts/phase34a4/`.
Recorded timings include the WSL UNC development checkout and are not
installed-local package performance claims.

## Olaa COPC

Source: `artifacts/phase34a2/olaa-index-qualification/view.copc.laz` within
the Windows workspace. Size: 1,425,693,643 bytes. Points: 104,819,538.
SHA256:
`bea135c4eca2e3db0dd0079575f2e250b52cefd58c873af7f6edfc11086f3f37`.
The source has no declared usable CRS; source-local coordinates were retained,
not assigned an invented EPSG code. Region center: 271743.8125, 2153113.818.
Area width/height: 30 source units.

Read-only extraction artifact: `olaa-copc-query-01/query-evidence.json`.

| View | Matching points | Display points | Query seconds |
| --- | ---: | ---: | ---: |
| Area | 405,101 | 200,000 | 0.671 |
| Slice, width 5 units | 65,088 | 65,088 | 0.454 |

The area display is sampled, not selection authority. The original file's
full SHA256 was verified before/after the query run.

Live artifact: `olaa-copc-linked-01/linked.json`.
The live profile uses width 4 units, unlike the read-only query above.
Area selection resolved 96,106 original points; profile selection resolved
25,165. One authoritative editor remained active across linked views.
Shared classification changes, undo/redo, and session reopening passed.
Warm Overview and Slice switches retained renderers and were observed in
0.50 and 0.25 seconds respectively. This includes telemetry polling.
The native slice screenshot was nonblank and showed the shared selection.
Loaded-node RGB reported valid variable values; this is not a whole-source
color audit.

The complete live canary passed in 398.406 seconds with no reported errors.
The first full-source export took 199.954 seconds; the second took 143.984
seconds. Both retained all 104,819,538 points, preserved dimensions/CRS/custom
VLR payloads, and matched the staged journal for all dimension values.
The source hash was unchanged. PDAL normalized the empty source system ID
to PDAL; compression/CRS/Extra Bytes layout records are regenerated.

First two-edit export SHA256:
`c6ae33fddafd50db85cacc004a40ff09984fdd74a5b5cfc252096e97baee21f7`.
Final three-edit export SHA256:
`86da8239adb36d455ba7a2110bb18a799c4deaede125152dcc22679e692af159`.
Final classification changes affected 89,389 records; class 9 contained the
25,165 profile-selected points. Export staging used a 5,974,713,666-byte
disk-backed array. One in-flight sample showed about 6.2 GB working set and
213 MB private memory; this is not a peak-memory benchmark.

Detach/dock host acknowledgments took 63/15 ms. The 6.25-second detach test
wait included opening Overview after session restoration, not just moving
the existing native surface. Redocking was observed within 250 ms.
All owned test workers reached terminal shutdown and partial export files
were absent from the final artifact directory.

The handoff check exercises the export-ready
signal; it does not run a scientific processing algorithm.

## EPT Bounded Queries

Source:
`//SDAVXTRA/X Drive/PROJECTS_2/Big_Island/ChangeHI_Trees/Dry_Forest/Data/Lidar/ept-full/ept.json`.
Reported repository points: 110,008,858,527; CRS: EPSG:6635.
EPT metadata SHA256:
`a84934f5ef6364db3406291f34e20e3c5b7cbec19545e5fb135a9478b5381a13`.
Artifact: `ept-linked-query-01/query-evidence.json`.
At center 215250, 2114750, a 30-by-30-unit area returned 6,851 points
in 1.047 seconds; the width-5 slice returned 1,177 in 0.203 seconds.
All matching points fitted within the 200,000-point display cap.
This run overlapped the independent Olaa export and is not an isolated
performance benchmark.

EPT identity verification covers metadata only, not every repository node.
EPT remains read-only; these queries do not authorize editing or export
of the original repository. Read-only EPT session persistence remains open.

## Live EPT Views

The new `scripts/testing/qgis_ept_linked_views_smoke.py` exercises the real
page and native renderers without an authoritative editor. On QGIS 3.44,
`ept-live-linked-01` passed in 22.656 seconds; on QGIS 4.0,
`ept-live-linked-qgis4-01` passed in 22.547 seconds. Area Detail displayed
6,851 points and the profile displayed 1,177. Native captures were nonblank.
Overview/Profile switching retained renderers, and detach/redock retained the
same native worker. These are automated operations, not human gestures.

Review identified misleading detached Undo/Redo/Classify availability.
Detached controls now follow authoritative editor readiness, busy state,
selection, and journal state from the moment the window is constructed.
EPT windows show an explicit view-only status. The strengthened QGIS 3.44
`ept-live-linked-02` canary asserted these controls stay disabled and passed
in 22.313 seconds. No editor worker started; metadata SHA256 remained
unchanged. This does not verify every EPT node or enable EPT editing.

All 19 Qt control tests passed on QGIS 3.44 and QGIS 4.0. The focused
QGIS-free tier ran 180 tests with 26 dependency skips and no failures.
The local tiny-LAZ `detached-control-editable-01` canary passed on QGIS 4
in 47.047 seconds, including shared edits and validated export, confirming
that read-only gating does not disable the supported editable workflow.

## Remaining Gates

- Human drawing, switching, detach/redock, and editing acceptance.
- Large raw LAS/LAZ live linked-view and verified view-cache reuse coverage.
- EPT read-only session persistence and human linked-view interaction.
- Resource pressure, 21 views, 100 creation/deletion cycles, alternating edits.
- Sixty-minute linked-workspace soak and full milestone validation.
- Actual scientific processing of an edited export.

Release state remains LINKED_VIEWS_EXPERIMENTAL.
