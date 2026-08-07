# Tiled CHM Polygon Mask Order

Scalable CHM uses the exact polygon to select relevant cores, but each work unit reads its complete buffered rectangle. Polygon crop inputs are omitted from the point read.

Order: rectangular read, HAG validation, buffered CHM, aligned core extraction, checkpoint, mosaic, exact polygon mask, final verification, registration. Required masking failure fails the product.


## Phase 28G Exact Polygon Completion

Required cores are selected by exact core/polygon area before reads. Sparse verified cores are mosaiced on the global grid, then the exact polygon mask is applied.
