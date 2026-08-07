# Exact Polygon Work-Unit Filtering

Polygon CHM planning first creates the globally aligned envelope grid, then measures each retained **core** rectangle against the normalized exact Polygon or MultiPolygon. Positive area is required; a boundary-only touch is excluded. The buffered read rectangle is recorded separately and never makes an otherwise excluded core required.

The plan preserves three counts: envelope-grid candidates, required cores, and `SkippedOutsidePolygon` cores. Each candidate records exact intersection area, core coverage percentage, buffered intersection, source coverage expectation, and the planning reason. Polygon holes subtract from intersection area.

The plan signature includes the polygon identity, grid, required/skipped membership, source identity, buffer policy, HAG method, repository kind, and product. Changing polygon membership therefore changes the plan while recovery can independently validate compatible completed cores.
