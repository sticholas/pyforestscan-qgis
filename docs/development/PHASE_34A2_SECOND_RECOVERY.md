# Phase 34A2 second recovery

## Preserved state

Recovery on 2026-09-08, branch develop, HEAD
`734bc8633a779beb3e919818e9373b1ede609f91`.
No reset, clean, checkout, deletion, commit or push was performed.

The complete tracked diff at entry contained only:
- PRODUCTION: ui/mission_control.py (Point Cloud destination and unload hook).
- TEST: test_phase28a_productization.py, test_phase28c_interface_compaction.py,
  test_phase28h_compact_workspace.py (intentional sidebar expectations).

Untracked inventory at entry:
- PRODUCTION: core/point_cloud/{asset_server,backend,runtime,view_policy}.py,
  viewer_runtime.json; ui/point_cloud_page.py; viewer/{host,prepare_source}.py,
  viewer/__init__.py, host.qml, viewer.html, viewer.js.
- PRODUCTION ASSETS: viewer/assets/manifest.json plus 28 explicitly hashed
  runtime assets/notices (3,582,333 bytes), including COPC/LASzip WASM,
  Potree, its runtime libraries, navigation images and license texts.
- TEST: test_point_cloud_{asset_server,runtime,view_policy}.py.
- DOCUMENTATION: PHASE_34A2_QGIS_POINT_CLOUD_BINDING_AUDIT.md and
  PHASE_34A2_RECOVERY_STATE.md.
- HARNESS: scripts/audit_point_cloud_bindings.py.

Windows workspace, outside the repository:
- HARNESS: phase34a2_page_smoke.py, embed_probe.py and fixture generator.
- PROTOTYPE: phase34a2_webengine_child.py/.qml, local_assets.py,
  potree_view.html and vendor_assets.py.
- TEMPORARY_RUNTIME: .phase34a2-viewer-runtime (rejected venv experiment);
  .phase34a2-potree-build (pinned research/build checkout and dev dependencies).
- TEST DATA/EVIDENCE: .phase34a2-fixtures, viewer_probe.json,
  phase34a2-page-*.json/.png, phase34a2-embed-*.png, child-frame.png and logs.
- Managed optional viewer runtime: backend/viewer/runtime.json points to its
  own immutable runtime. The scientific environment is separate and unchanged.
- Generated __pycache__ files are temporary, not package/commit contents.

Process inventory found no surviving isolated viewer processes.
The prior interactive run had a PNG but no final JSON. The shared renderer
stderr log was empty. Escape itself is not evidence of a renderer crash.

## Reproduced baseline

Exact focused command:
`python3 -m unittest discover -s tests -p 'test_point_cloud_*.py'`
Result: 34 passed, 0.446 seconds.

Exact regression command:
`python3 -m unittest tests.test_point_cloud_runtime tests.test_point_cloud_asset_server tests.test_phase28a_productization tests.test_phase28c_interface_compaction tests.test_phase28h_compact_workspace tests.test_phase33a_release_audit tests.test_phase33b_execution_hardening tests.test_pbm_processing_execution tests.test_advanced_processing`
Result: 81 passed, 0.474 seconds.

QGIS 3.44 startup smoke: 100 construction cycles, 100 navigation cycles,
four engine states, widths 420/500/620/800, no new scientific imports: PASS.

## Exit code 1: exact cause

An exception hook reproduced the existing shutdown path without changing it:

```text
File "phase34a2_page_smoke.py", line 56, in complete
    if page.worker and page.worker.isRunning():
RuntimeError: wrapped C/C++ object of type ViewerWorker has been deleted
```

The renderer had already produced its frame; Qt had deleted its completed
worker. The harness queried that deleted Qt wrapper while waiting for cleanup.
This is a harness lifetime error, not independent evidence of WebGL/QGIS/
scientific failure.

Fix: a Python-owned threading.Event records worker completion; the harness
polls the event instead of a Qt method. The page releases its worker reference
on unload, while the retained worker cleans up its own subprocess.

Reproducer after fix: LAS rendered 20,000 points, camera commands succeeded,
source SHA256 before/after matched, and the harness exited 0.
LAS SHA256: `b18bdb4c66e3fb186977ce77e9eb7e6514a3da8fccd6bd9019c3347ca991250f`.

## Continuing qualification

Attempt-specific stdout.log, stderr.log and viewer_run.json now preserve
stage boundaries, versions, exceptions and shutdown origin. Unknown final
state after a hard kill remains unknown, not a fabricated clean shutdown.
The promoted deterministic harness is
scripts/testing/qgis_point_cloud_viewer_smoke.py. Camera command checks do not
replace final human mouse/keyboard acceptance.

Subsequent session, failure-isolation, real large-COPC and installed-package
evidence is recorded in [Interactive Acceptance](PHASE_34A2_INTERACTIVE_ACCEPTANCE.md).
Authoritative selection and EPT remain pending. Human orbit/pan/wheel zoom
were subsequently confirmed by the user.
No beta completion claim is made here.
