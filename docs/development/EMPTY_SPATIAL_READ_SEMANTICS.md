# Empty Spatial-Read Semantics

Empty bounded reads are typed rather than treated as generic scientific failures.

- `SkippedOutsidePolygon`: zero exact core/polygon area; no worker, attempt, output, or warning.
- `CompleteNoData`: a required core was read successfully but legitimately contains no returns, or lies outside authoritative source coverage. It is a successful terminal state.
- `FailedEmptyRead`: points were expected but a prior success or read/network evidence indicates an unexpected empty result. It may trigger the empty-read breaker.
- `NeedsCoverageReview`: coverage evidence is insufficient to decide safely.

Expected NoData never enters the HAG failure category. The user-facing completion message may note that areas without returns remain NoData.
