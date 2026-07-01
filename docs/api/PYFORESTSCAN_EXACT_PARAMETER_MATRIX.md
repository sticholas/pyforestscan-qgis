# PyForestScan Exact Parameter Matrix

Phase 20C verifies the documented PyForestScan `calculate.py` API parameter by parameter against the QGIS Advanced Processing Toolbox. The official PyForestScan calculate API is the source of truth for this matrix.

Status meanings:

- **Exposed**: available as a user-facing Advanced Toolbox parameter.
- **Mapped internally**: supplied by the adapter because QGIS users should not provide the raw object directly.
- **Deferred**: valid PyForestScan parameter or workflow intentionally not exposed yet.
- **Not applicable**: not meaningful as a QGIS Processing parameter.

## Calculate Module Parity

| Function | Parameter | PyForestScan wording/default | Advanced Toolbox status | QGIS/adapter mapping | Rationale |
| --- | --- | --- | --- | --- | --- |
| `assign_voxels` | `arr` | input point array | Mapped internally | Adapter reads lidar with `handlers.read_lidar(..., hag=True)` and merges arrays before calling PyForestScan. | QGIS users select datasets, not in-memory arrays. |
| `assign_voxels` | `voxel_resolution` | voxel resolution | Exposed | Product algorithms expose X/Y resolution and vertical `voxel_height` where a 3D voxel stack is required. | QGIS raster products need explicit horizontal resolution; PAD/PAI/FHD/Canopy Cover/Point Density/Voxel Statistic expose vertical binning. |
| `calculate_chm` | `voxel_resolution` | required | Exposed | Advanced CHM exposes X resolution and Y resolution. | Exact CHM resolution control. |
| `calculate_chm` | `interpolation` | `nearest`, `linear`, `cubic`, `None`; default `linear` | Exposed | QGIS enum uses `none`, `nearest`, `linear`, `cubic`; builder maps `none` to Python `None`. | QGIS Processing enums cannot display a literal `None` cleanly. |
| `calculate_chm` | `interp_valid_region` | default `False` | Exposed | Advanced CHM boolean. | Direct API parity. |
| `calculate_chm` | `interp_clean_edges` | default `False` | Exposed | Advanced CHM boolean. | Direct API parity. |
| `calculate_pad` | `voxel_height` | default `1.0` | Exposed | Advanced PAD parameter `voxel_height`. | Direct API parity. |
| `calculate_pad` | `beer_lambert_constant` | default `1.0` | Exposed | Advanced PAD, PAI, and Canopy Cover expose the internal PAD Beer-Lambert constant. | PAI and Canopy Cover require PAD internally. |
| `calculate_pad` | `drop_ground` | default `True` | Exposed | Advanced PAD, PAI, and Canopy Cover expose drop-ground behavior. | Direct API parity for PAD prerequisite. |
| `calculate_pai` | `voxel_height` | required | Exposed | Advanced PAI parameter `voxel_height`. | Direct API parity. |
| `calculate_pai` | `min_height` | default `1.0` | Exposed | Advanced PAI minimum height. | Direct API parity. |
| `calculate_pai` | `max_height` | default `None` | Exposed | Advanced PAI optional maximum height. | Direct API parity. |
| `calculate_canopy_cover` | `voxel_height` | required | Exposed | Advanced Canopy Cover parameter `voxel_height`. | Direct API parity. |
| `calculate_canopy_cover` | `min_height` | default `2.0` | Exposed | Advanced Canopy Cover minimum height / canopy threshold. | Direct API parity with clearer QGIS label. |
| `calculate_canopy_cover` | `max_height` | default `None` | Exposed | Advanced Canopy Cover optional maximum height. | Direct API parity. |
| `calculate_canopy_cover` | `k` | default `0.5` | Exposed | Advanced Canopy Cover extinction coefficient `k`. | Exact scientific parameter exposed for experts. |
| `calculate_fhd` | `voxel_height` | default `1.0` | Exposed | Advanced FHD parameter `voxel_height`. | Direct API parity. |
| `calculate_fhd` | `min_height` | default `0.0` | Exposed | Advanced FHD minimum height. | Direct API parity. |
| `calculate_fhd` | `max_height` | default `None` | Exposed | Advanced FHD optional maximum height. | Direct API parity. |
| `calculate_rumple` | `cell_resolution` | required | Exposed | Advanced Rumple exposes CHM X/Y resolution and passes the resolved tuple to `calculate_rumple`. | QGIS users control horizontal cell size; tuple support preserves rectangular cells. |
| `calculate_rumple` | `min_height` | default `None` | Exposed | Advanced Rumple optional minimum height. | Direct API parity. |
| `calculate_point_density` | `per_area` | default `False` | Exposed | Advanced Point Density boolean `per_area`. | Direct API parity. |
| `calculate_point_density` | `cell_area` | default `None` | Exposed | Advanced Point Density optional `cell_area`; adapter supplies X * Y resolution when omitted. | PyForestScan accepts `None`; adapter fallback documents the implied raster cell area when area-normalizing. |
| `calculate_voxel_stat` | `dimension` | required | Exposed | Advanced Voxel Statistic string parameter `dimension`. | Experts can target any dimension present in the point cloud. |
| `calculate_voxel_stat` | `stat` | `mean`, `sum`, `count`, `min`, `max`, `median`, `std` | Exposed | Advanced Voxel Statistic enum with the documented values. | Direct API parity and validation. |
| `calculate_voxel_stat` | `z_index_range` | default `None` | Exposed | Advanced Voxel Statistic exposes minimum and maximum indexes, then maps to a tuple. | QGIS has clearer numeric controls than raw tuple entry. |
| `generate_dtm` | `resolution` | default `2.0` | Exposed | Advanced DTM resolution. | Direct API parity. |

## New Advanced Toolbox Algorithms

- **Advanced Point Density** exposes `per_area` and `cell_area`, and maps dataset input through `assign_voxels` before `calculate_point_density`.
- **Advanced Voxel Statistic** exposes `dimension`, `stat`, and optional `z_index_range` controls, and writes the returned 2D statistic as a GeoTIFF.

## Documented Internal Mappings

- In-memory array parameters such as `arr`, `voxel_returns`, `pad`, `chm`, and `ground_points` are never exposed as QGIS parameters. They are created by the adapter from selected lidar datasets and intermediate PyForestScan calls.
- Output writing is handled by the adapter with `handlers.create_geotiff` or plugin-owned multi-band writing for PAD. QGIS users provide output paths, not lower-level writer objects.
- Guided Mission Control remains simplified. Exact parity controls are intentionally confined to the Advanced Toolbox.

## Remaining Deferrals

No `calculate.py` function from the audited API reference is unaccounted for in the Advanced Toolbox after Phase 20C. Broader non-calculate workflows such as tiled processing, polygon-crop product variants, and visualization helpers remain documented in the Phase 20B coverage matrix because they require separate workflow design rather than simple parameter parity.
