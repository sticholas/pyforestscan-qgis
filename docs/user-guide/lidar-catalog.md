# LiDAR Catalogs

Polygon Area Processing uses a LiDAR catalog so large repositories do not need to be scanned for every polygon.

## When You Need A Catalog

Use a catalog when you want to process a polygon against a folder or repository that contains many LiDAR sources. The catalog stores source footprints and metadata in a small SQLite database with a spatial index.

Normal polygon processing requires a catalog. If no catalog exists, Mission Control shows **No Catalog** and offers **Build Catalog**.

## Build Or Update

1. Open Mission Control > Batch.
2. Choose **Polygon Area Processing**.
3. Choose the **LiDAR Repository**.
4. Click **Build Catalog**.
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
