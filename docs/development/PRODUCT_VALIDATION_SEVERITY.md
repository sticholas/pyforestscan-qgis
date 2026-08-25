# Product Validation Severity

`ProductValidationResult` is the authoritative readiness projection.

- `READY`: no warnings or blockers; processing may start.
- `NEEDS_ATTENTION`: warnings are retained, but processing may start.
- `BLOCKED`: one or more required conditions failed; processing must not start.

Fields are `product`, `ready`, `severity`, `blockers`, `warnings`, `information`, and `required_actions`. A global warning acknowledgement is intentionally not part of the contract.
