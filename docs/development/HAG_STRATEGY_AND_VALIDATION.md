# HAG strategy and validation

`HagSuitabilityReport` records finite/unique XY counts, XY ranges/rank, classification and ground counts, density when known, existing normalized dimensions, and DTM availability. Strategy order is existing normalized height, compatible DTM, suitable classified-ground bounded Delaunay, then explicit failure.

Rank-deficient XY and `All points collinear` are deterministic. The work-unit ID, statistics, original exception, and traceback are retained. Identical Delaunay execution is not retried. Alternative methods require scientific approval.
