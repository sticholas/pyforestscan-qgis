# Product Planner Example Outputs

These examples show the shape of Product Planner outputs. Values are illustrative
and are not scientific products.

## Example JSON

```json
{
  "processing_executed": false,
  "products": [
    {
      "product": "chm",
      "label": "Canopy Height Model (CHM)",
      "plan_status": "Ready",
      "estimated_outputs": [
        {"path": "products/chm.tif", "type": "GeoTIFF raster"},
        {"path": "products/chm_metadata.json", "type": "JSON metadata"}
      ]
    }
  ]
}
```

## Example CSV

```csv
section,product,name,value,status,message
parameters,,grid_resolution,1.0,,
product,chm,Canopy Height Model (CHM),Ready.,Ready,
output,chm,GeoTIFF raster,products/chm.tif,Ready,Future canopy height raster.
```

## Example HTML

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>PyForestScan Product Planner</title></head>
<body>
  <h1>PyForestScan Product Planner</h1>
  <h2>Requested Products</h2>
  <p>Canopy Height Model (CHM): Ready</p>
</body>
</html>
```
