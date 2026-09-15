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

The current UI still presents numeric bounds rather than a dual-handle slider;
the QGIS-free contract is in place first so a future slider cannot silently
change axis or selection scope.


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
