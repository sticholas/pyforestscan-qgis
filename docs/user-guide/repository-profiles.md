# Repository Profiles

Repository profiles document spatial organization that cannot be discovered safely by a shallow probe alone.

## Filename/Grid Profiles

A filename/grid profile defines:

- profile name
- filename regex
- X and Y capture groups
- tile width and height
- origin offsets, if needed
- CRS
- source extensions
- folder constraints, if needed
- approval status
- validation tolerance

Mission Control must not use a filename/grid profile unless it is explicitly approved and declares a CRS.

## Validation

Before using a profile in production:

1. Sample representative files across the repository.
2. Compare regex-derived bounds with header-derived bounds.
3. Confirm CRS and units.
4. Record the tolerance and the source of the convention.
5. Revalidate when the provider changes naming or tiling.

## Partition Profiles

A partition profile lists known repository partitions with bounds, CRS, estimated source count, current index status, and optional child catalog path. Polygon Area Processing can use this to index only intersecting partitions first.

Partition profiles are useful for county/state repositories, survey-year folders, provider tilesets, and network shares where a full first pass would take too long.

## Current Scope

Phase 27I adds the profile models and planning behavior. A full profile editor and provider-specific profile library remain deferred until real repositories are validated.

## EPT Profiles

EPT does not need a filename/grid profile. Select the EPT root, `ept.json`, or `ept-data`; the plugin normalizes the selection to one logical EPT source and uses built-in EPT spatial access.
