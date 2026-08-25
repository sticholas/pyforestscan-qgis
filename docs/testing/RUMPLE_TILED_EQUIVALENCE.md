# Rumple Tiled Equivalence

The synthetic tiled test splits a CHM, includes exactly one shared CHM cell at the boundary, computes patch fields independently, retains non-overlapping cores, and concatenates them. Dimensions, NoData mask, values, min/max/mean, and pixel positions equal the whole-array calculation; maximum difference and RMSE are zero for the fixture.

Real EPT/LAS adaptive mosaics and visual seam inspection remain live-validation items. They are not claimed passed by this array-level proof.
