# Phase 30C Advanced Control Audit

| Control | Owner/default | User decision | Applicability | Phase 30C disposition |
|---|---|---|---|---|
| Processing Profile | Planner; Automatic | Optional policy preference | All Batch | Retained |
| Execution Mode | Custom profile; Sequential/Parallel | Specialist override | Custom only | Hidden outside Custom |
| Maximum Workers | Adaptive ceiling | Specialist upper bound | Custom + Parallel | Retained conditionally |
| Parallel Safe confirmation | Scheduler guardrails | No | None | Removed from visible UI; software owns safety |
| Load outputs | Output policy; on | Optional opt-out | All Batch | Retained, default on |
| Stop on error | Batch executor; off | Sometimes | Independent files | Retained Advanced |
| Skip completed | Resume policy; on | Sometimes | Resume | Retained Advanced |
| Retry failed only | Resume policy; off | Sometimes | Recovery | Retained Advanced |
| Overwrite outputs | Conflict policy; off | Sometimes | Existing outputs | Retained Advanced |
| Exact raster mask | Polygon contract; on | Troubleshooting only | Polygon raster | Retained under Polygon Finalization |
| Mask engine | Automatic | Troubleshooting only | Polygon raster | Retained under Polygon Finalization |
| Crop extent | Mask policy; off | Specialist | Polygon raster | Retained under Polygon Finalization |
| Touched cells | Mask policy; off | Specialist | Polygon raster | Retained under Polygon Finalization |
| Retain intermediates | Recovery policy; off | Diagnostic | Polygon raster | Retained under Polygon Finalization |
| Mask failure policy | Fail product | Troubleshooting | Polygon raster | Retained under Polygon Finalization |
| Repository strategy | Repository planner; automatic | Specialist | Polygon repository | Retained only with repository selected |
| Recovery/diagnostics | Durable job system | Action after failure | Terminal/recoverable | Retained under troubleshooting |

Automatic, Conservative, and Performance profiles materially change the requested concurrency ceiling. The adaptive planner may always choose fewer workers. Advanced remains optional: normal execution uses automatic topology, primary-output loading, exact polygon masking, safe conflicts, and retained durable checkpoints.
# Phase 30D supersession

Execution mode, parallel confirmation, per-run output loading, and warning acknowledgement were removed. The optional Custom worker value is an upper ceiling only.
