# Automatic Height Normalization

Validated normalized Z is represented explicitly as `EXISTING_NORMALIZED_Z`. A plausible filename or header range only triggers bounded inspection; accepted Z is copied to `HeightAboveGround` in a durable prepared source. Otherwise the existing DTM, class-2 Delaunay, or SMRF/Delaunay precedence applies automatically.

PyForestScan forest metrics require `HeightAboveGround`; raw Z is not substituted. Phase 31A uses current PyForestScan/PDAL operations in this order: valid existing HAG, compatible DTM, Delaunay from observed class 2, validated SMRF then Delaunay, or an actionable block.

Generated HAG is validated for dimension presence, finite fraction, range, negative fraction, and ground values near zero. Slight negative values are retained and reported rather than silently rewritten.

Source-local Delaunay is allowed only with trusted linear-unit evidence. SMRF parameters documented in meters are converted for trusted foot-based coordinates. Coordinate magnitude and LAS scale/offset are never treated as unit evidence.

Upstream references: [PyForestScan preprocessing guide](https://pyforestscan.sefa.ai/usage/getting-started-import-and-preprocess/) and [filters API](https://pyforestscan.sefa.ai/api/filters/).

Phase 31B uses one canonical-metre conversion for metres, international feet, and US survey feet. After trusted units resolve, class-2 ground with adequate bounded-strata coverage proceeds automatically through Delaunay HAG and quality validation.

For eligible standalone CHM/Rumple, Phase 31C may use configured assumed units after metadata resolution fails. Reports identify SMRF windows, thresholds, interpolation distances, and buffers as unit-sensitive. Implausible HAG remains a scientific failure, not an overridable warning.
