# Source Alternative Detection

Polygon Prerun compares selected LAS/LAZ records for duplicate-like coverage. Classification is conservative:

- `INDEPENDENT`: spatial or record evidence differs.
- `POTENTIAL_ALTERNATIVE_REPRESENTATION`: point count and XY bounds match, sizes are within one percent, and filename plus catalog Z ranges support a prepared representation.
- `DUPLICATE`: point count, bounds, and byte size match.
- `UNKNOWN`: overlap is suspicious but insufficient for an automatic choice.

Filename text alone never proves identity. For the Phase 31I evidence, both Olaa files contain 104,819,538 points with identical XY bounds. The raw file has Z 813.179-870.024; `_Norm` has Z -7.078-23.643. Combined with near-identical size and the `_Norm` relationship, Prerun selects the prepared representation once and estimates 104,819,538 points.

Ambiguous cases remain visible as: "Two LiDAR files appear to represent the same area." Advanced source selection remains the override path.
