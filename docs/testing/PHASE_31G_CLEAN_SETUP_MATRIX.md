# Phase 31G Clean Setup Matrix

| State | UI | Processing behavior | Evidence status |
|---|---|---|---|
| No engine | Setup required / Set Up | No batch is created | Automated state model |
| Healthy engine | Ready | Product token is issued | Automated contract tests |
| Missing `pyforestscan.handlers` | Needs repair / Repair | Process stops before batch | Boundary and contract tests |
| Old protocol/build | Update or repair required | Token validation rejects launch | Automated drift tests |
| Setup succeeds | Ready automatically | No second manual Check | Service/UI structural tests |
| Two QGIS instances | Shared lock protects setup | Second instance refresh required | Manual Windows QA pending |

Clean Windows setup, console visibility, installation transaction rollback, and a real product run remain manual release-gate checks; they are not represented as passed by QGIS-free unit tests.
