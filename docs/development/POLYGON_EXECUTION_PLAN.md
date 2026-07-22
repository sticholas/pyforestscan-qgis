# Polygon Execution Plan

`PolygonExecutionPlan` is the Phase 27N preflight authority for Polygon Area Processing. Preflight builds it, manifests serialize it, and execution consumes the selected sources from the same report.

## Contents

- repository identity
- polygon spatial context and normalization report
- source selection result
- selected products
- shared Batch options
- polygon finalization options
- requested and effective concurrency
- spatial read, masking, output, and loading plans
- workload estimate
- structured warnings and blockers
- validation results
- deterministic plan signature

## Plan Signature

The signature includes repository identity, polygon geometry hash, CRS, products, Batch options, mask options, output folder, and backend readiness. When polygon, repository, products, settings, or output folder change, a new preflight produces a new signature.

Run buttons should only execute a current plan. The current implementation records and displays the signature; fuller stale-plan blocking across saved workspaces remains a follow-up.
