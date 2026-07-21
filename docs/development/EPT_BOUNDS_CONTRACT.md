# EPT Bounds Contract

Phase 27L defines one typed EPT bounds contract for polygon-driven EPT processing.

`EptBounds` is the source of truth for spatial read bounds. It stores `xmin`, `xmax`, `ymin`, `ymax`, optional `zmin`/`zmax`, `crs`, `source`, and whether the coordinates were transformed. Values must be finite, ordered, non-boolean numbers and must carry a CRS.

The final value passed to PyForestScan is created only at the adapter boundary:

```python
([xmin, xmax], [ymin, ymax])
```

or, for 3D reads:

```python
([xmin, xmax], [ymin, ymax], [zmin, zmax])
```

The nested coordinate ranges must be Python lists. PyForestScan stringifies this value before PDAL receives it, so list ranges produce the required square-bracket expression:

```text
([204988.883967812, 205580.438378822], [2144384.290553354, 2146573.21175823])
```

The rejected legacy shape was:

```python
((xmin, xmax), (ymin, ymax))
```

which stringified to parentheses inside each coordinate range and triggered PDAL errors such as `No opening '[' in range`.

Manifest round trip:

1. Mission Control stores `ept_bounds` as a JSON object.
2. PBM reconstructs `EptBounds`.
3. The adapter converts it to the final PyForestScan value.
4. Diagnostics may record a derived `pdal_bounds_expression`, but that expression is not the source of truth.

The grammar validator `validate_pdal_bounds_expression()` exists as a defensive diagnostic check and rejects malformed expressions before expensive point-cloud reads begin.
