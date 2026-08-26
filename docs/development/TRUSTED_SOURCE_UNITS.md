# Trusted Source Units

Standalone height preparation needs trustworthy linear distances, not necessarily an Earth-referenced CRS. Phase 31B supports three typed units:

- metres (`1.0` metre per source unit)
- international feet (`0.3048` metre per source unit)
- US survey feet (`1200/3937` metre per source unit)

Preparation parameters are stored canonically in metres and converted once through `LinearUnit.source_units`. Arbitrary text and coordinate-magnitude guesses are rejected.

When only units are assigned, PBM may inspect class-2 ground, create and validate HeightAboveGround, and produce CHM/Rumple in source coordinates. Outputs retain `crs=None` and record `SOURCE_SPATIAL_MODE=SOURCE_LOCAL`, source units, and preparation provenance. A real CRS is still required for polygon matching.
