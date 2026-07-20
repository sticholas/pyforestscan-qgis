# LiDAR Catalogs

Polygon Area Processing uses a LiDAR catalog so large repositories do not need to be scanned for every polygon.

## When You Need A Catalog

Use a catalog when you want to process a polygon against a folder or repository that contains many LiDAR sources. The catalog stores source footprints and metadata in a small SQLite database with a spatial index.

Normal polygon processing requires a catalog. If no catalog exists, Mission Control shows **No Catalog** and offers **Build Complete Repository Index**.

## Build Or Update

1. Open Mission Control > Batch.
2. Choose **Polygon Area Processing**.
3. Choose the **LiDAR Repository**.
4. Click **Detect Best Indexing Strategy**, then use **Build Relevant Index** when supported or **Build Complete Repository Index** for the durable full catalog.
5. After the catalog is ready, choose the polygon source, products, and output folder.
6. Click **Run Preflight Check**.

Use **Update Catalog** when files have been added, modified, or deleted. Unchanged files are skipped during update.

## What The Catalog Reads

The catalog reads headers and metadata only:

- LAS/LAZ/COPC: public header metadata when available.
- EPT: `ept.json` metadata only.

The catalog does not read full point clouds and does not crawl EPT data nodes.

## Automatic Polygon Bounds

You do not enter xmin/xmax/ymin/ymax manually. Mission Control derives those values from the selected polygon. The broad bounds make catalog and EPT reads fast. The exact polygon geometry is still used for clipping.

## Metadata Errors

Some files may fail metadata inspection. Mission Control records those failures in the catalog instead of ignoring them. If many sources could not be indexed, preflight warns that polygon source selection may be incomplete.

## Very Large Repositories

For repositories with millions of files, the first catalog build can take time. It is a deliberate maintenance step, not something that runs silently before every polygon job. Normal preflight queries the catalog and should remain fast.

## Responsive Large Repository Workflow

Selecting or pasting a LiDAR Repository path is lightweight. Mission Control normalizes the path, checks that it is accessible, and reads catalog status only. It does not recursively count files, inspect headers, calculate folder size, or build a catalog until you explicitly click **Build Relevant Index**, **Build Complete Repository Index**, **Update Catalog**, or **Resume Catalog Build**.

Use **Use Path** when a native folder picker is slow on network, removable, or mounted storage. Use **Quick Probe** for a bounded top-level sample: it stops after a small item/time budget and does not recurse. The sample is not a total file count.

Catalog jobs show stages, counters, elapsed time, current rate, and latest source path. Early progress is indeterminate because the total file count is unknown. The plugin does not invent an exact percentage before it has a reliable denominator.

## Pause Resume And Updates

Catalog work is checkpointed after safe chunks. **Pause After Current Chunk** lets the job finish the current chunk, commit records, write state, and mark the job interrupted. **Resume Catalog Build** continues without discarding valid indexed records.

**Update Catalog** skips unchanged files using relative path, size, and modified time. New and modified files are indexed incrementally. Deleted files are reconciled in SQLite rather than with a giant in-memory path set.

## Benchmarking Safely

Use `python3 scripts/benchmark_lidar_catalog.py --synthetic` for a safe SQLite/RTree benchmark. Use `--path <repo> --real-dry-probe` to probe a real repository without recursion. A real build requires `--real-build --confirm-real-build`, and can be bounded with `--max-files` or `--maximum-duration` for controlled testing.

## Adaptive Indexing Strategies

Before building a complete catalog, click **Detect Best Indexing Strategy**. Mission Control performs a bounded top-level probe and reports whether it can use an existing spatial index, a PDAL tile index, EPT/COPC native registration, an approved filename/grid profile, partitioned lazy indexing, or the full header catalog fallback.

Use **Build Relevant Index** when the detected strategy can register an existing index or native EPT/COPC source. Use **Build Complete Repository Index** when no trustworthy shortcut exists.

See [Choosing A LiDAR Index Strategy](choosing-lidar-index-strategy.md) and [Repository Profiles](repository-profiles.md).
