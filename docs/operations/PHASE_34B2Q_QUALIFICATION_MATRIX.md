# Phase 34B2Q Qualification Matrix

This matrix separates automated evidence from real QGIS, GPU, and human visual evidence.

| ID | Capability | Source | Automated evidence | QGIS evidence | Human evidence | Status | Failure / blocker | Fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RGB-01 | Dimension aliases and packed RGB availability | LAS/LAZ/EPT | RGBStats, fixture matrix, and resolver tests | Renderer telemetry exposes availability | Confirm color correctness | NEEDS_HUMAN_VISUAL | WebGL color appearance | 9fa8517 |
| RGB-02 | Missing/zero/invalid RGB diagnosis | Synthetic/render sample | Bounded RGB diagnostic model and executable fixture matrix | Diagnostic telemetry emitted | Confirm fallback appearance | NEEDS_HUMAN_VISUAL | Visual fallback | 9fa8517 |
| VIS-01 | Attribute mode availability | LAS/LAZ/COPC/EPT | Alias and unavailable-mode tests | Docked/detached controls sync available modes | Confirm wording | PASS_AUTOMATED | None | 9fa8517 |
| VIS-02 | Presentation range state | All viewer sources | Auto/robust/manual contracts | Renderer range commands | Confirm color ramp | NEEDS_HUMAN_VISUAL | GPU mapping | ea7cc6c |
| LEG-01 | Continuous legend and adaptive ticks | 3D/profile | Nice-tick and legend tests | Packaged overlays | Readability | NEEDS_HUMAN_VISUAL | Visual judgment | 2201eb0 |
| LEG-02 | Classification labels and visibility | LAS/LAZ/EPT | Shared color mapping, rendered swatches, and visibility toggle contracts | Legend is rendered in viewer | Confirm readability and color agreement | NEEDS_HUMAN_VISUAL | Canvas rendering | 8d5c6b1 |
| PROF-01 | Multi-segment distance and axes | Profile sources | Geometry/tick contracts | Profile axes rendered | Edit/cursor feel | NEEDS_HUMAN_VISUAL | Live QGIS interaction | 2201eb0 |
| PROF-02 | Profile source authority and stale rejection | Local LAS/LAZ | Validated drag/insert/remove, generation coalescing, and source-space contracts | Linked worker path | Rapid drag behavior | NEEDS_HUMAN_VISUAL | Full edit loop | 3121782 |
| ANA-01 | Visible View bounded analytics | Large sources | Renderer sample cap and telemetry | Overlay packaged | Update cadence | NEEDS_HUMAN_VISUAL | GPU/session soak | 9fa8517 |
| ANA-02 | Coalescing and bounded cache | Synthetic workload | 100-request, stale-order, eviction tests | Scheduler contract | Large-cloud soak | PASS_AUTOMATED | None | 9fa8517 |
| LIFE-01 | Detached state protocol | Small/large/EPT | Worker ownership, automatic profile requery/redetach, and cleanup contracts | QGIS tests remain skipped | Detach/redock | NEEDS_HUMAN_VISUAL | QGIS-dependent | 62b5db2 |
| LIFE-02 | View-switch sizing | Small/large/EPT | `scripts/qgis_point_cloud_viewer_stress.py` is an executable 50-cycle QGIS harness; contract tests run QGIS-free | Needs QGIS capture | 50-cycle stability | NEEDS_HUMAN_VISUAL | Live QGIS/GPU execution required | 34B2R |
| PERF-01 | Large-cloud interaction | Olaa-scale | Bounded renderer/cache contracts | No automated GPU test | 10-15 minute soak | BLOCKED_ENVIRONMENT | Real source/GPU required | -- |

## Required Human Pass

RGB visual correctness, legend readability, profile editing/cursor feel, detached/redock lifecycle, repeated view-switch geometry, and Olaa/EPT responsiveness remain human qualification items. The current build also requires the direct profile gesture check: drag endpoints/intermediate vertices, double-click a segment to insert, and right-click an intermediate vertex to remove. Save the viewer diagnostic snapshot and run record for failures.
