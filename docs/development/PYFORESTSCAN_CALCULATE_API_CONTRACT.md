# PyForestScan Calculate API Contract

Phase 32T audited the managed backend against the current [official calculate reference](https://pyforestscan.sefa.ai/api/calculate/) and the installed package call signatures. Mission Control uses a static release registry; it performs no runtime scraping and imports no scientific stack to render controls.

## Function inventory

| Function | Classification | Mission Control decision |
| --- | --- | --- |
| assign_voxels | Internal primitive | Never a product. Shared voxel resolution is exposed where required. |
| calculate_chm | User product | CHM raster. Interpolation is expert-configurable; valid-region and edge cleanup remain automatic for tiled safety. |
| calculate_pad | User product | Multi-band PAD raster. Voxel height is shared; Beer-Lambert coefficient and ground exclusion are contextual Advanced settings. |
| calculate_pai | User product | PAI raster. Shares PAD/voxel work and exposes integration height range. |
| calculate_fhd | User product | FHD raster. Exposes vertical bin height and canopy height range. |
| calculate_canopy_cover | User product | Canopy-cover raster. Shares PAD, with minimum/maximum height and extinction coefficient. |
| calculate_rumple | User product | Existing spatial Rumple raster plus scalar summary. Optional minimum canopy height is Advanced. |
| calculate_point_density | User product | Raster density per output-cell area by default. Raw counts are not mislabeled as points per area. |
| generate_dtm | User product | Ground-elevation raster. HAG preparation remains automatic and separate. |
| calculate_voxel_stat | Advanced operation | Retained in Advanced Toolbox; its generic dimension/statistic contract is not a normal checkbox. |

## Supported defaults

| Product | Parameter | Default | UI policy |
| --- | --- | --- | --- |
| Shared voxel products | Vertical bin height | 1.0 m | Contextual Advanced |
| CHM | Horizontal resolution | 1.0 plugin release default | Contextual Advanced |
| CHM | Interpolation | linear | Contextual Advanced |
| FHD | Minimum / maximum height | 0.0 / Automatic | Contextual Advanced |
| PAI | Minimum / maximum height | 1.0 / Automatic | Contextual Advanced |
| PAD | Beer-Lambert coefficient | 1.0 | Contextual Advanced |
| PAD | Exclude ground layer | True | Contextual Advanced |
| Canopy Cover | Minimum / maximum height | 2.0 / Automatic | Contextual Advanced |
| Canopy Cover | Extinction coefficient | 0.5 | Contextual Advanced |
| Rumple | Minimum canopy height | Automatic | Contextual Advanced |
| Point Density | Per unit area | True | Contextual Advanced |
| DTM | Resolution | shared output resolution | Automatic/shared |

Maximum-height controls use Automatic to mean the available canopy top. Explicit maximum values must exceed the associated minimum. Invalid ranges block Prerun/request construction with a direct explanation.

## Hidden automatic arguments

CHM valid-region interpolation and edge cleanup remain controlled by established tiled processing policy. DTM/HAG preparation, exact polygon clipping, bounds, coordinate transformation, source-local preparation, scheduler settings, and checkpointing remain internal. These are execution-safety concerns rather than scientific product choices.

## Dependencies and reuse

- PAI depends on PAD.
- Canopy Cover depends on PAD and PAI integration.
- Rumple depends on CHM.
- PAD, PAI, FHD, and Canopy Cover share voxel configuration.

Dependency resolution happens during Prerun/background execution. Checkbox interaction only changes configuration and marks the plan stale.

## Output semantics

The registry records display name, function, dependencies, output filename, output kind, units, parameter schema, and release-version basis. Polygon manifests record the actual scientific values used and whether they came from defaults or Mission Control overrides.
