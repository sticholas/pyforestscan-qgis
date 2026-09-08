# Phase 34A2 recovery state

Recovered on 2026-09-08 from HEAD
`734bc8633a779beb3e919818e9373b1ede609f91`, branch develop.
No reset, clean, checkout, deletion, commit or push was performed.
Tracked diff, diff stat and whitespace check were empty.

| File / location | Classification |
| --- | --- |
| core/point_cloud/view_policy.py | PRODUCTION_CANDIDATE: adaptive budget guardrails |
| tests/test_point_cloud_view_policy.py | TEST: six policy regressions |
| scripts/audit_point_cloud_bindings.py | PRODUCTION_CANDIDATE: reproducible diagnostic |
| docs/development/PHASE_34A2_QGIS_POINT_CLOUD_BINDING_AUDIT.md | DOCUMENTATION |
| Windows workspace phase34a2_embed_probe.py | PROTOTYPE: Qt host / child lifecycle |
| Windows workspace phase34a2_webengine_child.py and .qml | PROTOTYPE: isolated QML WebEngine |
| Windows workspace .phase34a2-viewer-runtime | DISPOSABLE_RUNTIME: isolated PySide6 6.11.2 wheels |
| Windows workspace phase34a2-embed-*.png and renderer log | PROTOTYPE evidence, not viewer acceptance |
| /tmp/pyforestscan-phase34a2-potree | PROTOTYPE research checkout; no code vendored |

Windows workspace: C:/Users/Milo/Documents/PyForestScan-QGIS.
The prototype uses a separate bundled development Python; it is not a
deployable plugin runtime and must not become a production-path dependency.

Exact focused command, from repository root:
`python3 -m unittest discover -s tests -p 'test_point_cloud_*.py'`.
Result: 19 tests passed in 0.012 seconds.
Coverage: 13 existing source identity, journal, session and capability tests;
six adaptive-budget tests. These are not live Qt or rendering tests.

Process inventory returned no running Python process with phase34a2 in its
command line. The latest Qt5/Qt6 child-owned probes reported child_exit 0.
The accidental Escape interruption is not classified as a renderer, QGIS,
scientific or Processing Engine failure.

Known unresolved boundary: a native child handle / scene-graph startup signal
did not establish visible WebGL content. Diagnose the existing probe's asset,
JS, exposure, geometry and first-frame state before changing architecture.
The user explicitly requires an embedded viewer; linked native QGIS 3D is not
the chosen substitute.
