# Dataset Explorer Example Outputs

These examples show the shape of Dataset Explorer outputs. Values are illustrative
and are not generated from reference scientific sample data.

## Example JSON

```json
{
  "dataset": {
    "format": "las",
    "is_remote": false,
    "metadata_source": "pdal-pipeline",
    "source_path": "plot.las"
  },
  "geometry": {
    "crs": "EPSG:32610",
    "estimated_density_points_per_square_unit": 2.0,
    "height_range": {
      "minimum": 1.0,
      "maximum": 28.0
    }
  },
  "point_statistics": {
    "classification_summary": [
      {"classification": 2, "count": 100},
      {"classification": 5, "count": 240}
    ],
    "dimensions": ["X", "Y", "Z", "Classification", "Intensity"],
    "point_count": 340
  },
  "supported_products": [
    {
      "label": "Canopy Height Model (CHM)",
      "product": "chm",
      "status": "Warning",
      "reason": "Z and ground class 2 are present; future HAG generation appears feasible."
    }
  ]
}
```

## Example CSV

```csv
section,name,value,status,message
dataset,source_path,plot.las,,
geometry,crs,EPSG:32610,,
statistics,point_count,"340",,
classification,2,100,,
product,Canopy Height Model (CHM),chm,Warning,Z and ground class 2 are present; future HAG generation appears feasible.
```

## Example HTML

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PyForestScan Dataset Explorer</title>
</head>
<body>
  <header>
    <h1>PyForestScan Dataset Explorer</h1>
    <p>plot.las</p>
  </header>
  <main>
    <section>
      <h2>Supported PyForestScan Products</h2>
      <p>Canopy Height Model (CHM): Warning</p>
    </section>
  </main>
</body>
</html>
```
