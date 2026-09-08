# Phase 34A ecosystem review

Initial research record, not a completed dependency-selection approval.
No third-party code copied. Runtime/platform claims below are upstream
descriptions unless explicitly marked locally probed.

## Primary sources and integration decisions

| Project | Runtime / formats / architecture | Selection, edits, persistence and scale | Decision / cost / risk |
| --- | --- | --- | --- |
| [QGIS](https://api.qgis.org/api/master/classQgsPointCloudLayer.html) | Native C++/Qt; point-cloud providers and 3D | Native edit buffer can write through provider; Python binding coverage differs | Reuse public host viewing APIs; source commits forbidden |
| [PDAL](https://pdal.io/en/stable/stages/filters.assign.html) | Managed native/Python pipelines; LAS/LAZ/COPC/EPT | Filter assignments; some stages stream; no editor session/undo | Existing engine candidate for replay/export; pipeline-specific memory validation |
| [COPC](https://copc.io/) | LAS 1.4 hierarchy | Node-local identity changes on reindex | Prefer existing hierarchy, no full materialization |
| [EPT](https://entwine.io/en/latest/entwine-point-tile.html) | JSON hierarchy and point nodes | Tree versioning needed; manifest alone insufficient identity | View streaming first; editing blocked on identity |
| [Untwine](https://github.com/hobuinc/untwine) | Native out-of-core indexing | Produces viewing representation; no journal UI | Managed cache candidate; converter/license lock pending |
| [Potree](https://github.com/potree/potree) | Browser WebGL hierarchy | Profiles/clipping, LOD; no equivalent source-safe journal adopted | Renderer candidate; web runtime/assets/security cost |
| [maplibre-gl-lidar](https://github.com/opengeos/maplibre-gl-lidar) | WebGL/deck.gl/COPC loaders; LAS/LAZ/COPC/EPT | Streaming colors/picking; not proven authoritative editing | Alternative renderer; audit JS/WASM bundle and QGIS embedding |
| [CloudCompare](https://github.com/CloudCompare/CloudCompare) | Native Qt/C++ local clouds | Mature segmentation/scalar tools; resident-cloud assumptions | Design reference, not in-process replacement |
| [Open3D](https://github.com/isl-org/Open3D) | Python/C++ geometry/viewing | Array-centric algorithms; no managed edit journal | Optional specialist only; native dependency/ABI cost |
| [segfix](https://github.com/tim-devereux/segfix) | QtPy/PyQt6, Vispy, NumPy/SciPy, laspy; PLY/LAS/LAZ | Label journal, lasso and working copies; full label arrays | Deep review below; no copying |
| [GeoLibre](https://github.com/opengeos/GeoLibre) | React/Tauri local-first layers | Plugin boundaries and local data; not QGIS journal | Design only; do not rewrite host application |
| [LiDAR AutoVector Studio](https://github.com/AkmaulHoque/world_lidar_feature_collector) | QGIS/PDAL derived surfaces | Presets/classification/feature candidates | Preserve trusted classes; license and engine-version gates |
| [PointCloudEditor](https://pointcloudeditor.com/) | Commercial editor | Product interaction reference | Proprietary; no source reuse, runtime internals unverified |
| [Global Mapper](https://www.bluemarblegeo.com/knowledgebase/global-mapper/Pro/SelectByClassification.htm) | Commercial GIS/LiDAR | Add/replace class selections and analysis controls | Behavior reference only, no code/assets |
| [Cesium](https://github.com/CesiumGS/cesium) | Browser globe/3D Tiles | Geospatial streaming, not exact source editing | Reference budgets/georeferencing; avoid second GIS stack |
| [PyForestScan](https://joss.theoj.org/papers/10.21105/joss.07314) | Existing scientific engine | Protected scientific calculations, not editing | Existing processing only; paper license is not code license |

Full candidate-specific undo/session/export implementation details, exact
transitive licenses and supported OS versions remain open when not documented
above. Do not infer feature absence from an uninspected implementation.

## segfix pinned source audit

Inspected commit `f4885ca6a9fb4bde8b7624d6e6d430771bfb7df1`:
LICENSE (MIT, Tim Devereux), pyproject.toml, model.py, treecatalog.py and
viewer/edit/save call sites. Python range is >=3.10,<3.13; Qt6 and native
render dependencies would add host compatibility cost.

Useful concepts: compact edit records, projected lasso, reversible labels,
review-centered navigation and project persistence. Its catalog retains
whole-cloud labels/original labels and its model uses coordinate arrays.
Working-copy memmap patching and decimation expansion do not establish our
exact full-resolution identity contract. Do not transplant that save model
or assume memmap alone proves bounded memory. No code copied.

## Actual QGIS probe

Windows QGIS 3.44.13-Solothurn: Qgs3DMapCanvas exists, but Python does not
expose setMapSettings. QgsPointCloudLayer exposes startEditing/supportsEditing
but not changeAttributeValue in the inspected runtime. This rules out blindly
translating current C++ API examples. Other installed versions were not
viewer-qualified in this milestone. QGIS 3.28, 3.34, 3.40, 4.0 and current
stable require separate live probes. Windows/Linux/macOS viewer qualification
remains pending, independent of prior Process UI compatibility.

[QGIS point cloud guide](https://docs.qgis.org/3.44/en/docs/user_manual/working_with_point_clouds/point_clouds.html)
and [LAS specification](https://www.asprs.org/wp-content/uploads/2019/07/LAS_1_4_r15.pdf)
inform attributes/classification. VPC/profile integration and newer LAS
revision differences still need implementation-specific review.

## Optional AI: research, not installation

| Candidate | Input/output and potential utility | Deployment gate |
| --- | --- | --- |
| [SAM](https://github.com/facebookresearch/segment-anything) | Image masks; projected suggestions, not source point labels | Torch; checkpoint-specific RAM/GPU, license/weights review |
| [DINOv3](https://github.com/facebookresearch/dinov3) | Image features, not direct 3D instance edits | Variant-specific weights and terms; no mandatory installation |
| [DeepForest](https://github.com/weecology/DeepForest) | RGB crown detections | Image-to-cloud registration and weights/domain validation |
| [StarDist](https://github.com/stardist/stardist) | Image/volume star-convex instances | Microscopy assumptions differ from irregular LiDAR |
| [Open3D-ML](https://github.com/isl-org/Open3D-ML) | Point-native ML pipelines | Torch/TF and native compatibility; optional pack only |
| [PointNet++](https://github.com/charlesq34/pointnet2) | Point-set classification/segmentation | Legacy/custom native operators; hardware benchmark required |
| [RandLA-Net](https://github.com/QingyongHu/RandLA-Net) | Point-native semantic labels | Framework/custom-op compatibility and trained-domain gates |
| [Pointcept](https://github.com/Pointcept/Pointcept) | Point-transformer segmentation | CUDA/sparse kernels and substantial optional dependency cost |

Model sizes, CPU viability and hardware budgets are not measured here and
must be recorded per selected checkpoint, not guessed per model family.
Every output remains a suggestion until explicit user acceptance.

See [reuse register](../development/PHASE_34A_THIRD_PARTY_REUSE_REGISTER.md)
and [backlog](EXTERNAL_REPOSITORY_RESEARCH_BACKLOG.md).
