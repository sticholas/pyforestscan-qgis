# Durable Source Preparation

Large local LAS/LAZ sources are prepared once inside the managed coordinator before tiled CHM or Rumple work begins. Preparation is automatic and is not a user workflow.

## Lifecycle

1. Build the union of required buffered work-unit read extents.
2. Inspect source dimensions and height evidence through the managed runtime.
3. Select the existing-HAG, validated-normalized-Z, DTM, class-2 Delaunay, or SMRF-plus-Delaunay strategy.
4. Materialize a local `prepared_hag.laz` with an explicit `HeightAboveGround` dimension.
5. Validate the prepared artifact, publish `status.json`, then run the canary and remaining work units.

The durable state is stored below `source_preparation/<source-id>/`. It records source identity, support extent, method, runtime contract, signature, artifact checksum, quality metrics, and timestamps. A process-owned lock prevents duplicate preparation. A lock left by a dead coordinator is recoverable.

No product work-unit scheduler is constructed until the status is `COMPLETE`, the artifact exists, and its path agrees with the status contract. Preparation failures therefore produce one `source_preparation` scientific blocker rather than repeated tile failures.

## Reuse

The preparation signature includes the source fingerprint, scientific method, CRS/unit context, and exact support extent. Exact compatible checkpoints are reused after interruption. A changed source or support extent receives a new artifact. Containment-based expansion/reuse is deferred; exact matching is intentionally conservative.

## Network Policy

For a network source, crop filters limit the materialized support artifact. Ordinary LAS/LAZ storage may still require the reader to scan the source stream; it does not provide COPC-style spatial seeking. Tiled products then read the local prepared artifact rather than repeatedly scanning the network source. Exact polygon masking remains a final raster operation; source preparation uses buffered rectangular support.
