# Rumple Scalar Equivalence

Automated fixtures cover flat canopy, analytical plane, peaks, corrugation, smooth random surfaces, NoData holes, `min_height`, non-square cells, and no-support arrays. The aggregate is `sum(surface_area)/sum(planar_area)`; with constant `dx*dy`, this equals the arithmetic mean of valid patch ratios.

The release tolerance is `1e-10 * max(1, abs(upstream_scalar))` for float64 calculation. Flat fixtures equal 1, analytical planes match `sqrt(1+(dz/dx)^2+(dz/dy)^2)`, and increased corrugation amplitude increases Rumple.
