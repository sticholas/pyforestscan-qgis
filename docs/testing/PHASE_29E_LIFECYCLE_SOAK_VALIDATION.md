# Phase 29E Lifecycle Soak Validation

The QGIS-free soak executes 50 consecutive logical current-job cycles mixing complete, failed, cancelled, and scientific-blocker states. Every cycle injects a stale callback and verifies rejection, exactly one current token, current-only output publication, bounded active state, and no stale result paths. Historical records accumulate intentionally as immutable history; active timers/processes are not created by this state-level test.

Offscreen QGIS validation separately covers plugin construction and runtime integration. A destructive QGIS crash/process-tree soak remains a live release-matrix item.
