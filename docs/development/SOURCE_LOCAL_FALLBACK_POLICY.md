# Source-Local Fallback Policy

Unknown spatial metadata is not automatically a scientific blocker. `resolve_processing_spatial_context` owns one application policy for eligible standalone products. The default is metres, represented as:

- CRS: none
- units: metres
- basis: `ASSUMED_SOURCE_LOCAL`
- confidence: `ASSUMED`
- authoritative: false
- georeferenced: false
- processing mode: `source_local`

This is a processing assumption, not discovered evidence or CRS assignment. It never changes source LAS/LAZ bytes.

## Eligibility

Fallback currently applies to independent standalone CHM and Rumple jobs when CRS and units are unresolved, evidence is not contradictory, no polygon/cross-source alignment is requested, and preparation otherwise has a defensible scientific path. Explicit file/repository units and CRS always take precedence.

Fallback is prohibited for polygon alignment, reprojection, map-coordinate transformation, incompatible cross-source operations, and products outside the declared source-local fallback capability set. Those workflows require confirmed spatial meaning.

## Configuration and identity

Tools & Setup offers metres, international feet, US survey feet, or **Require explicit assignment**. The user-local choice is stored in `spatial_policy.json`. Unit, basis, authority, CRS, and preparation method are frozen into requests and checkpoint signatures. Assumed metres therefore cannot share HAG checkpoints with trusted metres or feet.

Scientific quality gates remain unchanged. Ground coverage, finite values, negative-HAG fraction, height range, and preparation completion can still block or escalate a run.
