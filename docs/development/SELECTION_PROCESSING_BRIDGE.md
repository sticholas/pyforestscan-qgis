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
for each registered product. The Mission Control launcher and request translation
remain the next implementation slice. Until that wiring is validated, the
existing explicit export-to-Process handoff remains the qualified route for
edited derivatives.
