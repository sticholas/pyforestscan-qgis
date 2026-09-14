# Phase 31D Selection Strategy Equivalence

Direct header scan and verified catalog selection consume the same effective repository CRS before spatial comparison. Catalog rows retain raw metadata; the assignment is applied at query/result time.

Equivalence means both strategies use the same transformed polygon envelope, inclusive overlap equation, effective source CRS, and selected physical paths. Strategy discrepancies remain visible in the polygon manifest and are not hidden by automatic fallback.

EPT and COPC retain their native metadata resolution paths, while shared assignments and conflict rules apply wherever raw member metadata requires them.
