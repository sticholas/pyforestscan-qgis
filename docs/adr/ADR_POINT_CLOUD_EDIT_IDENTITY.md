# ADR: Point cloud edit identity

Status: accepted for foundation; export implementation gated.

Never address authoritative edits by displayed sample order. Reordering,
decimation and camera-dependent LOD invalidate that identity.

The implemented first selection contract is an inclusive XYZ box in source
CRS, optional ORIGINAL classification filter, and full source SHA256.
It is explicitly not a lasso. Selection membership must be resolved at full
resolution against original attributes; later edits cannot change membership
retroactively. Ordered journal operations resolve overlapping assignments;
undo removes the last active operation and requires recomputing its overlay.

| Candidate | Decision |
| --- | --- |
| LAS record index | Stable only for identical bytes/order; viable future exact mask |
| LAZ logical record index | Needs full-resolution decoder addressing, not byte offsets |
| COPC node/local index | Binds to exact octree; invalid after reindex/conversion |
| EPT node/local index | Needs immutable node manifest/content versions, not ept.json alone |
| Extra Bytes ID | Use only after proving uniqueness, persistence and source association |
| Source-space query | Chosen first contract; original fields, explicit CRS and boundary rule |
| LOD sample mask | Preview only; never silently promoted to full-cloud edit |

The foundation rejects EPT file fingerprints rather than misrepresenting
ept.json as proof of the whole tree. EPT editing stays blocked until immutable
node identity or a fully versioned source snapshot is implemented. Remote
ETags alone are not necessarily content hashes.

Polygon/frustum selection requires validated source-space geometry and
explicit edge inclusion. Do not substitute an envelope for a polygon.
Selection by current edited class requires frozen membership or explicit
journal-revision replay; it is not supported by the first contract.
