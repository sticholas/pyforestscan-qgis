# Point cloud export status

Edited LAS/LAZ/COPC export and Use Export in Process are pending implementation.
No source file is modified by the foundation contracts.

The planned exporter writes a new cloud, validates attribute preservation and
compares source fingerprints before/after. It must report format-specific
limitations instead of silently dropping attributes. Existing scientific
raster/table output behavior is unchanged.
