# Project Vision

PyForestScan QGIS will provide the official-feeling QGIS interface for
PyForestScan without replacing or duplicating the PyForestScan Python library.

The plugin should help users generate forest structural products from airborne
lidar through QGIS Processing workflows that are discoverable, documented, and
repeatable.

## Vision Statement

Make scientifically credible lidar-derived forest structure products accessible
to QGIS users through a maintained Processing plugin that uses PyForestScan as
its computational engine.

## Non-Goals

- Reimplement PyForestScan algorithms.
- Hide scientific assumptions from users.
- Couple the plugin to unstable PyForestScan internals.
- Prioritize visual convenience over reproducible Processing workflows.

## Guiding Principles

- QGIS Processing first.
- PyForestScan remains the engine.
- User choices must be explicit and reproducible.
- Outputs must be named, typed, and documented.
- Validation should happen before long-running computation starts.
- Scientific results should be traceable to inputs, parameters, versions, and
  methods.

