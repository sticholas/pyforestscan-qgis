# Phase 34A3 - Non-destructive editing loop

## Release state

**EDITOR_EXPERIMENTAL**. Version remains 0.2.0-beta.1.
This continuation builds on f72a5485f1347de40493a1e5cc6b1cd864037370.
It is not Phase 34A4, a public release, or a claim of complete human acceptance.

## Implemented contract

- Polygon and Rectangle produce source-XY geometry in an orthographic top view.
  Pointer/Esc returns to perspective navigation. Replace/Add/Subtract are explicit;
  Shift/Alt at gesture start select Add/Subtract within the viewer only.
- Immediate renderer previews are not selection authority. The existing managed
  SelectionResolver resolves original points, independent of display LOD.
- Selection freezes original-class and source-Z filters. HAG/numeric filters
  remain supported by the core, but this UI does not expose a new HAG editor.
- The existing session journal now carries resolved attribute operations:
  Classification, explicit Low Noise 7/High Noise 18, Withheld, and
  DELETE_ON_EXPORT. Ordered replay always tests original attributes.
- Selection/staged colors are separate resident-node overlays. Original source
  files and resident classification buffers are not rewritten. Preview work is
  culled by cloud-relative node bounds and sliced across animation frames.
- Undo/redo moves the journal cursor. Metadata autosaves after completed edits,
  undo/redo and exports, inside the user-local viewer editor-runs folder.
- Save/Open Session use the same schema and retain legacy region operations.
  Source relocation requires the exact saved fingerprint. Changed sources are
  not automatically rebased. Editing Details exposes recovery and diagnostics.
- A separate managed scientific child performs hashing, selection, export and
  verification. QGIS does not import scientific modules for the editor.
- Export creates a NEW LAS/LAZ plus an adjacent .export_validation.json sidecar.
  Existing targets, source aliases/hardlinks, waveform formats and unqualified
  COPC destinations are blocked. Session save is not cloud export.
- Export replays an STRtree-indexed execution plan over 65,536-point chunks,
  stages records in a disk-backed NumPy mapping, and uses the already installed
  PDAL writer. No package upgrade or alternate writer was introduced.
- Every output dimension/value is compared to a second source/journal replay.
  CRS, custom VLR payloads, counts and hashes are checked before publication.
  PDAL regenerates compression/CRS/Extra Bytes layout records. Empty header IDs
  may receive writer defaults; differences are recorded as header_normalizations.
- Cancellation is cooperative; a native compression step may finish before
  cancellation is acknowledged. Normal failures remove owned temporary files.
  Abrupt process death may leave visibly named .partial files; do not treat
  these as completed exports or delete unrelated files during recovery.
- Use in Process rechecks the export fingerprint in the managed child, selects
  only that file in Process, preserves the output preference, and does not run
  processing. Active Process work blocks replacement. Original/derived paths,
  session ID, export ID and hashes remain in the validation sidecar and current
  handoff state; not every scientific report format copies those IDs yet.

## Recorded evidence, 2026-09-08

Evidence root on the test machine:
C:/Users/Milo/Documents/PyForestScan-QGIS/artifacts/phase34a3

| Gate | Evidence |
| --- | --- |
| Twenty mixed, overlapping edits | editor-process-canary/editing_acceptance.json; classification, noise, withheld, removal, undo/redo, save/load |
| Independent output reference | Every LAS/LAZ dimension matches a separately calculated original-array rectangle reference on the 20,000-point fixture |
| Original fixture immutability | LAZ SHA256 4672454a0036298308d7f1e5fbfad3548340061dbb96ff924b2fc7632c234866 unchanged |
| Export failure safety | Source overwrite, existing target, missing folder, disk full, cancel before/after staging, injected writer-boundary failure rejected with journal/source intact |
| Extra dimensions | dimension-preservation: NIR, double FutureScore, uint64 TreeID beyond 2^53, custom PFS_QA:42 VLR and normal LAS flags preserved in LAS and LAZ |
| Process regression | Managed CHM succeeded on both ordinary and extended-dimension edited LAZ, without changing scientific algorithms |
| Qt integration | QGIS 3.44.13/Qt5 and QGIS 4.0.0/Qt6 deterministic editor canaries; authoritative count 814 and matching display/export class totals |
| Recovery and density | editor-ui-failure-layout: 420/600/760/1100/1400 widths, no editor control overflow; owned renderer terminated after saved edits, journal retained and overlay restored |
| Startup isolation | 100 constructions, 100 navigation cycles, four engine states, no new QGIS scientific imports |
| Full large-source export | olaa-full-edit-export-retry/large_edit_acceptance.json; 104,819,538 points, 20,405 selected, exact independent PDAL crop count, full LAZ export validated |
| Large export duration | 125.328 seconds overall; 119.594 seconds inside export |
| Large memory | Peak private bytes 277,512,192; working set 6,258,659,328; disk staging 5,974,713,666 bytes |
| Large source SHA256 | Existing COPC bea135c4eca2e3db0dd0079575f2e250b52cefd58c873af7f6edfc11086f3f37 unchanged |
| Large output SHA256 | ea4ae7ac065c5557976d82c1bd52d8fb495185f5c56029ba7c9da86be1be91cf |
| Original raw Olaa LAS | Rehashed unchanged: dda1c1bab4da2a6c41cb620bc2fc1f256f4920714ac30bcde826aa963208fc67 |

The first large attempt failed on an explicitly empty system_id option, after
disk staging but before publication. Its evidence is retained under
olaa-full-edit-export. The corrected writer omits unsupported empty options and
records the normalization from an empty system ID to PDAL.

The memory mapping avoids a source-sized private NumPy allocation, but does NOT
guarantee a tiny resident working set. File-backed pages may remain resident.
Low-memory machines and multi-billion-point full exports are not qualified.

## Journal benchmark

Source validation passed 1,088 tests with 10 platform/dependency skips in WSL;
the managed Windows point-cloud tier passed all 73 focused tests. Compilation,
undefined-name checks and Markdown links passed. Existing unused help-topic
registrations remain advisory; no used topic or generic placeholder was missing.
The final extended-dimension run also exercised nonzero Synthetic, KeyPoint,
Overlap and Withheld flags, return fields, source IDs and GPS time.

Cursor-only latency is distinct from autosave, geometry replay and painting.

| Edits | Saved bytes | Median undo / redo | Save seconds | Private bytes after save |
| --- | --- | --- | --- | --- |
| 100 | 132,244 | about 0.001 / 0.001 ms | 0.0113 | 25,661,440 |
| 1,000 | 1,314,845 | about 0.001 / 0.001 ms | 0.0556 | 29,863,936 |
| 10,000 | 13,149,846 | about 0.001 / 0.001 ms | 0.5006 | 39,579,648 |

These measure the journal, not 10,000-edit renderer latency. The editor does not
discard audit history for compaction. Export's indexed execution plan is derived
from the unchanged ordered journal.

## Remaining gates

1. Human Polygon/Rectangle drawing, modifiers, Esc, orbit/pan/wheel regression,
   staged colors, undo/redo, save, actual QGIS close/restart, reopen, export,
   reopen the exported cloud, Use in Process and a small CHM.
2. EPT editing remains deliberately disabled. The earlier real EPT viewer
   qualification is not an immutable edit-source contract. A safe bounded
   snapshot/node-identity workflow is still required.
3. COPC edited output and waveform formats are not qualified; LAS/LAZ are the
   current export targets. Automatic large unindexed LAS/LAZ preparation remains
   outside this continuation.
4. Forced export-worker death/retry, filesystem publication failures, crash
   remnants, very large overlays and low-memory operation need broader coverage.
5. Linux/macOS embedded adapters and installed-profile Qt6 human editing are not
   qualified. No claim of universal QGIS/OS support is made.
6. Selection detail UI reports available class/Z/HAG/bounds evidence; complete
   intensity/return statistics, full-source Data Health and fast classify mode
   are not delivered by this slice.
7. Human clean-ZIP editing acceptance remains separate from source/harness and
   automated package/import checks. Do not publish a 0.3 editor release yet.

Lasso is deferred until Polygon/Rectangle human acceptance is solid. Brush,
profile and segment editing remain later-phase work: they must emit the same
source-space SelectionDefinition contract, never renderer indices. Brush needs
an explicit radius/depth/filter/stroke contract; profiles need a source-CRS
corridor; segments need authoritative original attribute names and identity.

## Manual acceptance script

Use a new output folder and retain the source SHA256. Do not test against an
unsaved user project.

1. Open Point Cloud and a local LAS/LAZ or qualified COPC; confirm normal orbit,
   pan and wheel zoom.
2. Choose Polygon; draw a small region in the top view and complete the polygon.
   Check preview, authoritative count, classes and Editing Details.
3. Select Ground (2), Apply, inspect the staged color, Undo, then Redo.
4. Clear Selection. Draw a Rectangle. Test Replace, Add and Subtract; test
   viewer-focused Shift/Alt and Esc without stealing QGIS shortcuts.
5. Stage explicit Low Noise, High Noise, Withheld and Remove on Export on small
   overlapping regions. Review the compact history.
6. Move the camera, set original-class/Z filters, Save Session to a named file.
7. Close QGIS, restart, open that session. Confirm source verification, camera,
   colors, filters, journal/history and overlays. Do not export to recover.
8. Test Reload Viewer. Recovery must not erase edits or break Process.
9. Export a NEW LAZ, inspect the validation sidecar, reopen that LAZ and inspect
   classifications/flags/counts. The original SHA256 must match.
10. Use in Process, confirm only the export is selected and the prior output
    folder is retained. Processing must not start automatically.
11. Run a small CHM explicitly, inspect outputs/provenance and verify no orphan
    viewer/editor child remains after closing Mission Control.
12. Record QGIS/Qt/Windows versions, installed ZIP SHA, screenshots, exact
    failures and human pass/fail. Automated camera commands are not mouse QA.
