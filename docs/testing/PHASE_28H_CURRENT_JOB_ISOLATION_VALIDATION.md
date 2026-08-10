# Phase 28H Current Job Isolation Validation

Automated status: **Passed**.

- Job A completes and becomes history when B starts.
- B starts with empty current Results.
- Late A callbacks cannot mutate B.
- A outputs are ineligible for automatic loading while B is current.
- Exactly B terminal outputs are accepted.
- A second Process click while active is blocked.
- Clearing a result archives it and resets current status.
- Historical recovery requires an explicit controller action.

Interactive QGIS test with two real coordinators and layer-count evidence: **Not tested live**.
