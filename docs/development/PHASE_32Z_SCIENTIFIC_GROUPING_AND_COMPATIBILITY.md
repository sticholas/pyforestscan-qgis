# Phase 32Z Scientific Grouping and Compatibility

## Root cause

Phase 32Y rebuilt one global pair of `QFormLayout` columns and greedily placed
each active scientific group into the shorter column. Product headings were
temporary labels recreated on every toggle. Qt deferred their destruction,
and old maximum-height constraints could survive a larger rebuild. The result
was semantic mixing, transient blank row shells, detached generic labels, and
compressed editors.

## Final Advanced model

Advanced Scientific Settings now owns persistent vertical groups in this
order: Shared Settings, CHM, DTM, PAD, PAI, FHD, Canopy Cover, Rumple, and Point
Density. DTM is omitted because it has no separately exposed override in this
surface. A group with no active rows is hidden and contributes no header,
margin, separator, or body height.

Each group may use two internal form columns at wide widths. Groups are never
balanced beside unrelated products. Controls are persistent across layout
changes, and every editor has a stable key such as `fhd.min_height` plus a
product-qualified accessible name. Theme-derived editor and group size hints
prevent Qt from compressing controls while allowing the Process page to scroll.

PyForestScan Calculation Guide remains in the stable Advanced footer with
Restore Defaults.

## Scientific contract

The managed runtime was inspected directly on 2026-09-03. PyForestScan 0.4.1
exposed these relevant signatures:

| Product | Function | User-facing Advanced contract |
| --- | --- | --- |
| CHM | `calculate_chm` | grid resolution; interpolation (`linear` default) |
| DTM | `generate_dtm` | shared output resolution; no separate Advanced group |
| PAD | `calculate_pad` | voxel height; Beer-Lambert constant `1.0`; drop ground `True` |
| PAI | `calculate_pai` | voxel height; minimum `1.0`; maximum automatic |
| FHD | `calculate_fhd` | voxel height; minimum `0.0`; maximum automatic |
| Canopy Cover | `calculate_canopy_cover` | voxel height; minimum `2.0`; maximum automatic; `k=0.5` |
| Rumple | `calculate_rumple` | grid/cell resolution; minimum height automatic |
| Point Density | `calculate_point_density` | per-area normalization |

PAD dependency parameters used internally by PAI or Canopy Cover retain their
defaults but do not create a visible PAD group unless PAD itself is selected.
PyForestScan source and calculations were not modified.

## Visual matrix

The package was exercised in real Windows QGIS at narrow, normal, and wide
widths for CHM; CHM+FHD; CHM+PAD; CHM+FHD+PAD; CHM+FHD+Canopy Cover;
CHM+PAD+PAI; all products; and collapsed Advanced. This produced 24 captures
per QGIS runtime.

Both QGIS 3.44.13/Qt 5.15.13 and QGIS 4.0.0/Qt 6 passed with:

- stable group order and product ownership;
- zero visible empty groups;
- zero horizontal overflow;
- no value migration after repeated toggles;
- one internal column below 760 px and two above it;
- full native editor heights; and
- collapsed Advanced height of 28 px.

QGIS 3.44 averaged about 2.4 ms per toggle before the final size correction;
QGIS 4.0 averaged 3.36 ms. Both remained below the 10 ms target.

## Keystone compatibility evidence

| QGIS line | Evidence | Classification |
| --- | --- | --- |
| 3.34 | Official release/API generation reviewed; no runnable local install | NOT TESTED |
| 3.40 | Local 3.40.5/3.40.15 setup stubs were not runnable QGIS installs | NOT TESTED |
| 3.44.13 | Full 24-case UI matrix; existing engine and exact CHM canary evidence | SUPPORTED WITH LIMITATIONS |
| 4.0.0 | Full 24-case Mission Control UI matrix under Qt 6 | UI-COMPATIBLE |
| 4.2.2 | Current release identified; no local installation | NOT TESTED |

Official QGIS release history confirms 3.34 and 3.40 as prior API generations
and 4.0 as the Qt 6 transition. See the [QGIS 3.34 changelog](https://qgis.org/project/visual-changelogs/visualchangelog334/),
[QGIS 3.40 changelog](https://qgis.org/project/visual-changelogs/visualchangelog340/),
[QGIS 4.0 release announcement](https://blog.qgis.org/2026/03/09/qgis-4-0-norrkoping-is-released/),
and [current downloads](https://qgis.org/download/).

`qgisMinimumVersion=3.28` remains an installability declaration. It was not
lowered or promoted to a support claim because no older live matrix passed in
this phase. No maximum version is declared.

## Processing Engine evidence

Micromamba 2.8.1 was invoked with isolated roots for dry-run solves of
`win-64`, `linux-64`, `osx-arm64`, and `osx-64`. Resolution did not complete in
the bounded validation window and was stopped without creating an environment.
The YAML files therefore remain range specifications, not solved locks.

No current archive URLs or SHA-256 values were guessed. Exact locks, pinned
Micromamba artifacts, macOS/Linux install and repair tests, current QGIS 4.2
execution, and cross-platform numerical-equivalence evidence remain release
gates.
