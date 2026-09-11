# Selection Processing Bridge

The viewer's authoritative selection is now representable as a
SelectionProcessingScope. It carries the original source path and fingerprint,
closed source-space geometry, view/scope kind, resolved source-point count, and
optional elevation or HAG limits.

This is a value contract, not a second selection authority and not yet a
promise that every product can execute directly from every scope. A future
product launcher must validate the source fingerprint again, translate the
scope into the product request's bounded polygon and height fields, confirm
that the selected product supports the scope kind, run through the normal
PBM/Processing Engine path, and record the scope summary in the processing
report.

The intended flow is:

select area/column/profile -> review source-point count and height range ->
choose product -> review product-specific requirements -> run

Product-specific eligibility is now represented as AVAILABLE or REVIEW guidance
for each registered product. The Point Cloud editor now has an explicit
**Prepare Product** action. It creates this contract from the latest
authoritative selection and routes to Processing for review; it does not start
a job, mutate the source, or silently choose a product. Product-specific
request translation and execution remain the next implementation slice. Until
that wiring is validated, the existing explicit export-to-Process handoff
remains the qualified route for edited derivatives.

Processing displays a prepared scope as a review-only label containing its
scope kind, source-point count, vertical limits, and the statement that
processing has not started. Clearing or replacing the processing context must
not create a second selection authority.

The request contract intentionally stops before execution.

The Processing page now exposes the registered product choices for a prepared
scope. **Prepare Selected Product** creates a serializable
`SelectionProductRequest` containing the product, source identity, source-space
geometry, bounds, vertical filter, point count, output folder, and review
status. It is a review artifact only: no PBM job is launched and no source
points are changed. Profile raster requests are visibly marked for scientific
review rather than being presented as automatically safe.
The selected product can also be materialized as a separate review JSON artifact containing one product and the authoritative scope. The base Product Plan is never overwritten. Processing blocks the normal Start action while a selected scope is active until bounded PBM execution is validated; **Use Whole Dataset** returns to the established route.
The pipeline context can now rehydrate a scoped review plan and expose its source-space envelope plus the existing PolygonExecutionInput transport model. This is translation evidence only; product pipeline steps do not consume the scope until bounded reads, CRS handling, and PBM preflight are validated.
The CHM pipeline now has the first guarded consumer boundary: a plan marked READY_FOR_EXECUTION passes the scope envelope and polygon transport into ChmRequest, while REVIEW_ONLY plans fail closed with an actionable PipelineContextError. Whole-dataset plans remain unchanged.
