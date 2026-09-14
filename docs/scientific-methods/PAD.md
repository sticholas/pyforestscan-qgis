# Plant Area Density (PAD)

## What It Measures

Vertical plant area distribution as a 3D X/Y/height-bin volume.

## PyForestScan API Used

`assign_voxels`, `calculate_pad`

## Key Parameters

X/Y resolution, `voxel_height`, `beer_lambert_constant`, `drop_ground`.

## Authoritative Output

The plugin writes PAD as a multiband GeoTIFF. Each band is one vertical height bin. Phase 27D records band descriptions and dataset-level metadata for voxel height, Beer-Lambert constant, `drop_ground`, height-bin count, band-to-height mapping, and units.

## Derived Visualizations

PAD height slices, maximum projections, mean projections, and integrated PAD rasters are plugin-derived visualizations from the complete PAD volume. They are single-band GeoTIFFs for display and review; they do not replace the authoritative multiband PAD output.

## QGIS Display

PAD loads as a representative grayscale height slice by default. Optional RGB height-band composites must be interpreted as visualization composites, not as the authoritative metric.

## Quality Checks

Review band count, band descriptions, height-bin metadata, and derivative settings before interpretation.

## Reproducibility

Record the input dataset, CRS, XY resolution, voxel height, Beer-Lambert constant, `drop_ground`, PyForestScan version, QGIS version, and plugin version when using this product in analysis.
