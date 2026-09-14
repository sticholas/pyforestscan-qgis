# Contextual Spatial Reference UI

Spatial reference is per-source job metadata, not a global Processing Engine setting.

The Process page normally shows no spatial-reference panel. `SOURCE_UNITS_UNKNOWN` reveals only meter, foot, and US survey foot choices. Unknown polygon/source CRS, coordinate mismatch, alignment, or ambiguity blockers reveal only **Use Project CRS** and **Choose Coordinate System**. Unrelated blockers do not reveal spatial controls.

Selecting a trusted assignment stores it through the source-local policy store, hides the intervention, and immediately reruns preflight. Current files, folder or polygon, products, resolution, and output folder remain unchanged. Engine setup and source spatial resolution remain independent readiness dimensions.

