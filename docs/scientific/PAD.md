# Plant Area Density (PAD)

PyForestScan PAD is a three-dimensional product: X by Y by vertical height bins. PyForestScan QGIS preserves that dimensionality as the authoritative product.

## Authoritative Output

The authoritative PAD output is a multiband GeoTIFF:

- One band per vertical height bin.
- Shared CRS, XY grid, extent, and resolution with the requested product grid.
- Band descriptions record the represented height interval.
- Dataset metadata records voxel height, Beer-Lambert constant, `drop_ground`, band count, band-to-height mapping, and units.

PAD must not be treated as inherently single-band. Single-band rasters derived from PAD are visualizations or summaries, not replacements for the PAD volume.

## Derived Visualizations

Phase 27D adds QGIS plugin-derived PAD visualization helpers:

- Height slice.
- Maximum PAD projection over a vertical range.
- Mean PAD projection over a vertical range.
- Integrated PAD over a vertical interval.

Integrated PAD is not renamed PAI and should not be interpreted as native PAI. It is a plugin-derived integral of the PAD volume over the selected range.

## Default Display

The default QGIS display for PAD is a representative grayscale height slice. Optional height-band RGB composite support remains available as a visualization helper, but it is not the authoritative PAD metric.
