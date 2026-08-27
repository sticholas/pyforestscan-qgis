# Phase 31J Large-Source Preparation Regression

The production failure used one 104,819,538-point LAS, CHM plus Rumple, nine candidate areas, eight required areas, and one outside-polygon area. Runtime handoff succeeded, but each required tile failed at zero scientific runtime because `_ensure_hag_for_product()` rejected a large in-memory preparation.

The regression now verifies source preparation before scheduler construction, support bounds in preparation identity, explicit normalized-Z handling, durable artifact prerequisites, source-level failure, original/prepared path diagnostics, and preserved `SkippedOutsidePolygon` semantics.

The complete 104.8-million-point source was not run during automated validation because its UNC path was unavailable. The next live run should capture preparation duration, local artifact size, canary values, tile timing, and final outputs without a second click.

## Managed-runtime benchmark

A Windows managed-engine smoke used 50,000 synthetic points with validated normalized Z. Preparation completed in approximately 0.125 seconds, produced a 213,310-byte bounded LAZ, and checkpoint reuse completed in approximately 0.078 seconds. CHM values ranged from -0.05 to 8.95 metres; CHM-derived Rumple values ranged from approximately 1.00065 to 8.86662. This validates method routing and reuse, not 104.8-million-point throughput.
