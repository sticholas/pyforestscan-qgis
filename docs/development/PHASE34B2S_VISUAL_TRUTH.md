# Phase 34B2S: Visual Truth and Scientific Overlays

Status: IN PROGRESS

This phase hardens the point-cloud workspace around a simple rule: a visual
claim must be backed by the source attributes, a real product output, or
explicit provenance.

## Implemented in the current slice

- Viewer display modes resolve source aliases to Potree's canonical shader
  attribute names.
- Classification uses stable ASPRS labels for known classes and a deterministic
  categorical fallback for observed unknown classes.
- Continuous display modes expose named palettes without changing source data.
- Intensity uses the continuous gradient path rather than a misleading
  grayscale-only branch.
- Return Number and Number of Returns use discrete return-aware colors.
- Main and detached viewers preserve their Color By list instead of rebuilding
  it on every telemetry update.
- Product visualization descriptors identify whether an existing output is a
  raster surface, voxel field, scalar patch, or profile-capable source.
- Product descriptors require an output file and carry source fingerprint, CRS,
  range, NoData, and provenance metadata.

## Scientific boundary

The viewer does not synthesize CHM, DTM, PAD, PAI, FHD, Rumple, canopy-cover,
Point Density, or Voxel Statistic values. Those products remain authoritative
only when their real PBM output and provenance are available. The descriptor
registry is a routing and presentation contract, not a calculation engine.

Height Above Ground is not exposed as a display mode until a derived HAG
attribute is present in the loaded view and has a dedicated renderer binding.
This avoids presenting source elevation as HAG.

## Qualification remaining

Human qualification still needs varied-RGB, classification, intensity, return
number, palette, product-overlay, height/elevation selection, profile-axis,
and large-source evidence. QGIS-free contract tests cover the current
bindings and output descriptors; they do not replace a real WebGL/QGIS run.


## Precision interaction contract

Vertical selection is explicit about its axis: source elevation Z or Height
Above Ground. A one-unit band is a one-source-unit interval, not a camera
pixel depth. Linked views carry the view identity, slice thickness, axis, and
range together so a shape remains interpretable when it is mirrored into
another view.

The selection page now presents a dual-handle range control alongside
committed numeric bounds. Dragging or keyboard adjustment updates the local
control, while the authoritative source query is committed on release or
editing completion rather than for every partially typed character.


## HAG and profile evidence

Stored native or prepared `HeightAboveGround` attributes now use Potree's
source-attribute path and the attribute's own range. A source without a real
HAG dimension is not silently colored as HAG. The managed HAG contract
separates native, compatible cached, derivable, preparation-required, and
unavailable states, with cache identity tied to source, method, scope, and
parameters.

Vertical profiles now expose adaptive distance/elevation ticks and a restrained
grid based on the profile's authoritative geometry and vertical limits. The
axis labels distinguish source elevation from Height Above Ground.


## Product overlay availability

Product overlays use explicit availability states: `AVAILABLE_CACHED`,
`AVAILABLE_CAN_CALCULATE`, `CALCULATING`, `REVIEW_REQUIRED`, and
`NOT_AVAILABLE`. The state contract never starts a calculation on hover or
because a menu opened. Product descriptors carry support geometry and
product-specific domains: canopy cover is a fraction from 0 to 1, PAD is a
height-binned area-per-volume field, Rumple is a surface-area ratio, and Point
Density is points per output-cell area.


## Cached scientific overlay slice

Point Cloud now exposes a **Scientific Overlay** action once a source is open.
The user chooses an existing registered GeoTIFF; the page samples a bounded grid
through QGIS's raster provider and sends the grid to the isolated renderer. The
viewer displays it as a spatial surface with product label, units, value range,
CRS, and source/output provenance. The sample is capped at 96 by 96 cells so a
large raster cannot freeze the viewer.

This is intentionally a cached-output path. Opening the control never starts
CHM, DTM, PAD, PAI, FHD, Rumple, canopy-cover, Point Density, or Voxel
Statistic calculation. A DTM may use its sampled values as a terrain surface;
other products remain colored spatial surfaces and are never inserted into the
point attribute list. Outputs whose names do not identify a registered product
or whose source fingerprint cannot be checked are rejected with a visible
message.

PAD and Voxel Statistic overlays require an explicit selected raster band when the output is multiband. The band index is retained in the overlay legend and provenance; no multiband product is silently collapsed into an unlabeled scalar.
