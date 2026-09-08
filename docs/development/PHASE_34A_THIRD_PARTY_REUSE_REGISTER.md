# Phase 34A third-party reuse register

No upstream source code or new runtime dependency has been incorporated.
All foundation code is new local contract code.

| Source | Decision | Basis / outstanding gate |
| --- | --- | --- |
| segfix | DESIGN_REFERENCE_ONLY | MIT source inspected at f4885ca6a9fb4bde8b7624d6e6d430771bfb7df1; whole-cloud arrays and working-copy writes unsuitable here |
| QGIS | LIBRARY_DEPENDENCY_ALLOWED | Existing host API; probe Python bindings; never commit native source edits |
| PDAL | LIBRARY_DEPENDENCY_ALLOWED | Existing managed engine dependency; no new code vendoring |
| COPC / EPT | DESIGN_REFERENCE_ONLY | Format contracts; implementations require separate dependency/license audit |
| Potree / maplibre-gl-lidar | LICENSE_REVIEW_REQUIRED | No bundle selected; audit transitive assets and offline/security requirements |
| GeoLibre / CloudCompare / Open3D / Untwine | DESIGN_REFERENCE_ONLY | Architectural research only; no imported implementation |
| world_lidar_feature_collector | LICENSE_REVIEW_REQUIRED | Do not copy before pinned source/license review |
| Global Mapper / commercial PointCloudEditor | DESIGN_REFERENCE_ONLY | Proprietary; no code/assets copying permitted |
| AI and data-tool candidates | LICENSE_REVIEW_REQUIRED | Model weights, transitive dependencies and deployment terms unapproved |

Before copying any section record repository URL, file, pinned commit, exact
license, local destination, changes and attribution here. A permissive root
license alone does not approve every asset, model weight or dependency.
