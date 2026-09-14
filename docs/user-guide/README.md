# User Guide

The main user guide remains at [docs/USER_GUIDE.md](../USER_GUIDE.md). This section provides a stable entry point for future topic-specific user documentation.

Recommended reading order:

1. [Quick Start](../getting-started/QUICK_START.md)
2. [Mission Control](../ui/MISSION_CONTROL.md)
3. [User Guide](../USER_GUIDE.md)
4. [Scientific Methods](../scientific-methods/README.md)
5. [Known Limitations](../KNOWN_LIMITATIONS.md)

## Pages

- [Dataset Page](dataset.md)
- [LiDAR Catalogs](lidar-catalog.md)
- [Process LiDAR Folder by Polygon](polygon-folder-processing.md)
- [Choosing A LiDAR Index Strategy](choosing-lidar-index-strategy.md)
- [Repository Profiles](repository-profiles.md)


## Contextual Help

Mission Control uses one compact help strip. Hovering over a control or moving
keyboard focus to it updates the same explanatory text; standard tooltips and
accessible names remain available.

## Phase 27M Polygon Output Notes

- [Process LiDAR Folder by Polygon](polygon-folder-processing.md) covers exact raster masking and output loading.
- [Contextual Help](contextual-help.md) covers the new Batch Advanced help badges.

## Phase 27N Polygon Guidance

See [Process LiDAR Folder by Polygon](polygon-folder-processing.md) for the guided Polygon workflow and no-coverage recovery actions.

## Current Mission Control behavior

Polygon, product, resolution, repository, and output changes refresh optional Scientific Advisor guidance automatically. Use Advanced Toolbox to open QGIS Processing and inspect PyForestScan provider status.

## Compact Batch workflow

Choose folder or polygon processing, select LiDAR data and area, choose products
and an output folder, run Prerun Check, then Process LiDAR. Repository recognition,
spatial preparation, scheduling, checkpointing, and final clipping are automatic.
One compact Advanced section retains resolution, intermediate retention, and
repository maintenance for expert use.
