# Phase 31D Polygon Assignment Regression

The sanitized regression models the clean-machine Olaa failure:

- raw LAS CRS: unknown
- repository assignment: `EPSG:6635`
- LAS bounds: X `271368.874-272118.751`, Y `2152762.757-2153464.879`
- polygon CRS: `EPSG:6635`
- polygon bounds: approximately X `271371-272114`, Y `2152760-2153460`

Expected result: effective source CRS `EPSG:6635`, numeric overlap true, at least one logical input, and readiness proceeds to preparation. Removing the assignment blocks with `Use Project CRS` / `Choose CRS`; conflicting embedded metadata blocks rather than inheriting the repository CRS.

Automated coverage is in `tests/test_phase31d_processing_parity.py`.
