# Dataset Footprint Preview

Phase 12A adds a visual Dataset page preview for the inspected lidar extent. The
feature uses bounds already produced by Dataset Explorer and keeps QGIS APIs in
the UI integration layer.

## Implementation Choice

An embedded `QgsMapCanvas` inside Mission Control is deferred. Embedding a second
map canvas in a dock adds lifecycle, CRS synchronization, layer-set management,
and rendering risks that are not necessary for the first preview workflow.

Phase 12A implements the staged fallback:

1. Display a text footprint preview in Mission Control.
2. Add an in-memory footprint polygon layer to the current QGIS project.
3. Zoom the main QGIS map canvas to the footprint.
4. Keep the Dataset Explorer HTML report one click away.

## Data Source

The footprint is built from `DatasetExplorerReport.bounds`:

```text
xmin = bounds.min_x
xmax = bounds.max_x
ymin = bounds.min_y
ymax = bounds.max_y
```

The rectangular polygon coordinates are:

```text
(xmin, ymin)
(xmax, ymin)
(xmax, ymax)
(xmin, ymax)
(xmin, ymin)
```

Approximate area is `(xmax - xmin) * (ymax - ymin)` in source map units. Center
point is the midpoint of the rectangle.

## QGIS Integration

UI helper module: `pyforestscan_qgis/ui/qgis_footprint.py`.

- `preview_from_report(...)` is pure Python and unit tested without QGIS.
- `add_footprint_layer(...)` imports QGIS APIs only inside the function and adds
  an in-memory polygon layer named `PyForestScan Footprint - <dataset stem>`.
- `zoom_to_footprint(...)` transforms the source rectangle to the current QGIS
  project CRS when source and target CRS are valid and different.

The footprint layer is styled with transparent blue fill and a visible outline.

## CRS Behavior

- Known CRS: the memory layer is created with the source CRS, and QGIS handles
  map display. Zoom transforms the source rectangle to project CRS when needed.
- Unknown CRS: the preview displays a warning. The layer can still be added in
  source coordinates, but zoom is disabled in Mission Control because map CRS
  transformation cannot be trusted.
- Transform failure: the zoom action reports a clear warning message in the
  Dataset page preview text.

## Scope Boundary

Core adapter and Dataset Explorer logic remain QGIS-free. No scientific
processing changed. CHM and Canopy Cover processing continue to run through
JobManager, Pipeline, and the adapter.

## Manual QGIS Test

1. Open Mission Control.
2. Select a LAS, LAZ, COPC, or EPT dataset and output folder.
3. Run Dataset Explorer.
4. Confirm the Dataset page Spatial Preview shows CRS, extent, area, center, and
   warnings if any.
5. Click `Add Footprint Layer`.
6. Confirm a layer named `PyForestScan Footprint - <dataset stem>` appears in the
   QGIS layer tree with transparent fill and visible outline.
7. Click `Zoom to Footprint`.
8. Confirm the main QGIS map canvas zooms to the footprint.
9. Click `Open Report` and confirm the Dataset Explorer HTML report opens.
10. Test a dataset with unknown CRS, if available, and confirm the warning is
    clear and zoom is disabled.

## Limitations

- No embedded dock map canvas in Phase 12A.
- The preview uses the rectangular dataset bounds, not a convex hull or true
  point-cloud coverage mask.
- Area is reported in source CRS map units and is approximate.
- Unknown CRS footprints can be added in source coordinates but are not safe to
  zoom automatically.
