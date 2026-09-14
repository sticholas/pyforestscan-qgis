# PBM Spatial Reference Contract

Protocol 2 serializes coordinate state as:

```json
{
  "mode": "source_local",
  "crs": null,
  "resolution_source": "none",
  "confidence": "none",
  "transformation_required": false,
  "coordinate_units": "unknown"
}
```

`resolved` requires a valid CRS. `source_local` requires `crs: null`; strings such as `"None"` and `"unknown"` are canonicalized to null. Source-local processing retains X/Y coordinates, performs no reprojection, and is valid only when no polygon or other spatial alignment is requested.

Source-local GeoTIFFs contain transform, dimensions, resolution, and NoData but no assigned CRS. Tags include `PYFORESTSCAN_SPATIAL_REFERENCE_MODE=SOURCE_LOCAL`, `SOURCE_CRS_RESOLVED=false`, `SOURCE_COORDINATE_UNITS=unknown`, and `CRS_ASSIGNMENT_REQUIRED_FOR_SPATIAL_ALIGNMENT=true`.

