# CHM tiled equivalence report

Status: automated structural validation passed; live numerical equivalence pending.

Tests verify common dimensions/origin/resolution, contiguous cores, buffer-removal contract, verified-input mosaicing, deterministic merge policy, and exact-mask ordering. They are not scientific numerical-equivalence evidence.

Live comparison must cover small EPT, irregular polygons, LAS boundaries, dense/sparse canopy, flat/sloped terrain, and holes. Record valid cells, min/max/mean, RMSE, maximum absolute difference, edge differences, and seam maps before approving tolerances.
