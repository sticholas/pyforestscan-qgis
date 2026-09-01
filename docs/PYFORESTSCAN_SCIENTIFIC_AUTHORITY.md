# PyForestScan Scientific Authority

PyForestScan is the scientific authority for official forest-structure products in this plugin. Every official metric must ultimately invoke a supported PyForestScan API, and output provenance must record `scientific_source = pyforestscan` plus the installed PyForestScan version.

## Permitted plugin optimization

The plugin may optimize repository discovery, metadata indexing, spatial selection, bounded I/O, immutable caches, scheduling, process isolation, checkpointing, retry, mosaic orchestration, exact output masking, and QGIS output loading. Those changes may alter execution cost and failure containment, but not scientific meaning.

## Prohibited silent change

The plugin must not silently modify PyForestScan formulas, metric definitions, documented parameters, HeightAboveGround meaning, or official calculation code. A different algorithm, trained model, approximation, downsampled input, or altered dimension set is a separate derived product and must never masquerade as an official PyForestScan metric.

`HeightAboveGround` is scientifically distinct from raw `Z`. PyForestScan documentation requires it for forest metrics and documents either an existing dimension, Delaunay HAG from classified ground, or a co-registered DTM path. See the official [import and preprocessing guide](https://pyforestscan.sefa.ai/usage/getting-started-import-and-preprocess/) and [metric example](https://pyforestscan.sefa.ai/examples/calculate-forest-metrics/).

## Validation rule

Acceleration is acceptable only when a reference run and accelerated run use the same supported PyForestScan API and parameters, required dimensions, CRS, HAG contract, raster grid, NoData policy, and exact polygon mask. Equivalence evidence must cover numeric values, dimensions, georeferencing, and provenance.
