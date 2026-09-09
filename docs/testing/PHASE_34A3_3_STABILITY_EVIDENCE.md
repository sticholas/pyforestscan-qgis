# Phase 34A3.3 Stability Evidence

Release state: **VIEWER_STABILITY_EXPERIMENTAL** while the final gates below are
being evaluated. No 34A4 tooling, version bump, or release tag is authorized.
Starting HEAD: d8eb705 on develop, with preserved uncommitted Phase 34A3.2 work.

Raw evidence is retained outside the repository in the Windows workspace under
artifacts/phase34a3_2 and artifacts/phase34a3_3. Stress outputs, edited QA clouds,
cache files and screenshots are not committed. Tests used QGIS 3.44.13 / Qt5 and
4.0.0 / Qt6 on the current Windows workstation, not a clean installed-profile test.

## Gate record

| Gate | Status | Evidence / limitation |
| --- | --- | --- |
| A Motion visual quality | Human PASS | Small LAZ, Olaa and EPT orbit/pan/zoom confirmed by user |
| B Raw dense LAS/LAZ | PASS on measured sources | Automatic 104.8M LAS and LAZ intake; original-source selection/export |
| C COPC | PASS on measured source | Native 104.8M hierarchical viewing, no duplicate full index |
| D EPT viewing | Human PASS | 110B repository, requested nodes only; not full materialization |
| E 60-minute soak | FAILED geometry gate | 14,351 samples, 601 mixed transitions, 74 geometry flags; see 34A3.4 follow-up |
| F Source switching | PASS | 50 same-page Qt6 switches, no owned renderer orphans |
| G Session switching | PARTIAL | Existing saved-session/reload canary; multi-session repeated UI soak pending |
| H Viewer failure recovery | PARTIAL | Existing edited-state kill/reload canary; expanded run pending |
| I Export crash recovery | PASS with limitation | Owned child killed during actual 104.8M write; retry validated; partial scratch retained |
| J EPT editing semantics | BLOCKED | Immutable affected-node identity and bounded edit/export contract absent |
| K Human drawing | FAILED then fixed in 34A3.4 | Rectangle passed; Polygon completion failed; corrected-build human retest passed |
| L Human editing/export | PARTIAL | Rectangle reclassification passed; manual export not explicitly confirmed |
| M Process regression | PASS | 100-edit reference export followed by managed CHM succeeded |

## Filter invariants

Five hundred transitions passed independently in Qt5 and Qt6. Canvas, camera,
20k draw budget, selection, editor revision and child-widget count stayed fixed.
Qt5 canvas: 736 x 530; Qt6: 736 x 506. Actions included panel show/close, hover
help, Z filter, classification, clear and color mode. The panel remained one
owned nonmodal tool dialog. Human acceptance of the changed panel is separate.

The initial mixed soak harness also measured geometry across selection and clear
commands; those intentionally show/hide editor controls. Its raw geometry flags
must be classified by action, not silently discarded or called filter failures.
The separate 500-transition test holds selection state fixed.

## Source lifecycle evidence

The successful 525.687-second Qt6 run switched 50 times among tiny LAS, tiny LAZ,
the real 2.287M LAZ, native 104.8M COPC and EPT. Render modes, class/Z filters,
selection and journals did not leak. Read-cache reuse was exercised. Old render
processes were checked with creation timestamps, not PID alone.

An earlier attempt stopped after 13 cycles because its PID-only test mistook
recycled Windows identifiers for orphan processes. The first attempt is retained;
the corrected birth-identity run passed. No unrelated process was terminated.

## Export and editing evidence

The legacy raw selection guard was exposed by the first original-Olaa test and
removed only after confirming the resolver's 65,536-point, no-prefetch path.
The retry matched independent PDAL at 20,405 selected points and validated all
104,819,538 exported records. Original SHA256 remained unchanged.

One hundred independent-reference mixed edits passed classification/noise,
withheld, removal, per-cycle undo/redo/autosave, session reopen and LAS/LAZ export.
Cancellation, missing output folder, writer-boundary error, simulated full disk,
source-overwrite and existing-output rejection also passed. The UI-worker/overlay
100-cycle run is recorded separately and is not inferred from this core test.

The abrupt-export harness killed only its child during nonempty output writing.
No final output or validation sidecar existed after death. The source and saved
journal were unchanged; explicit retry to the same destination validated all
records. The killed attempt left 5,974,713,666 bytes of disk staging and a
586,211-byte partial LAZ, retained as clearly named QA evidence. Automatic
reclamation of such orphan scratch is not qualified.

See the [dense pipeline profile](PHASE_34A3_2_DENSE_VIEW_PIPELINE_PROFILE.md) for
the measured memory composition, first/second-open timings and corrected cache
flag-preservation defect.

## Blocking and unqualified work

- EPT remains view-only. Required next work is immutable affected-node content
  identity, bounded source partitions, mutation detection, journal binding,
  full-resolution selection and local derivative export with no tree writes.
  Removing the existing guard or hashing only ept.json is not acceptable.
- Human drawing/editing/export acceptance must be recorded, not inferred from IPC.
- Multi-session stress, graphics-context recovery injection and low-memory
  behavior require explicit evidence. No claim of complete weak-hardware support.
- Dedicated 100/125/150/200 percent multi-monitor DPI testing, Linux/macOS embedded
  adapters and an independent localized terrestrial scan are not qualified.
- A two-hour soak is not yet performed. Do not treat shorter evidence as that gate.
- Final full-suite, package-source identity, isolated ZIP smoke and release checks
  are pending until the milestone is complete.
