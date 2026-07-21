"""Central Mission Control contextual help topic registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpTopic:
    """One reusable contextual help topic."""

    key: str
    title: str
    short_text: str
    detailed_text: str
    recommended_default: str = "Use the recommended default unless your data requires otherwise."
    consequences: str = "Changing this can affect processing behavior or interpretation."
    common_mistake: str = ""
    documentation_anchor: str | None = None
    category: str = "general"
    keywords: tuple[str, ...] = ()
    applies_to_guided: bool = True
    applies_to_advanced: bool = False


HELP_TOPICS: dict[str, HelpTopic] = {
    "home.backend_status": HelpTopic("home.backend_status", "Backend status", "Shows whether the managed PBM backend can run routed processing.", "PBM is the preferred execution backend for routed products. If it is Ready, users do not need PyForestScan or PDAL installed in QGIS Python for those products.", documentation_anchor="docs/user-guide/contextual-help.md", category="Home"),
    "workspace.folder": HelpTopic("workspace.folder", "Workspace folder", "The workspace stores session state, reports, and run history.", "A workspace is different from an output folder. It helps Mission Control resume context and find recent reports; product outputs can still be written elsewhere.", category="Workspace"),
    "workspace.output_root": HelpTopic("workspace.output_root", "Output root", "Default location for generated products and run folders.", "Use an output root with enough disk space. Network output folders may be slower and can make long jobs harder to recover.", category="Workspace"),
    "dataset.source": HelpTopic("dataset.source", "Dataset source", "The point-cloud or EPT/COPC dataset to inspect.", "Dataset Explorer reads metadata and lightweight summaries before processing. For EPT, choose ept.json or the root folder; internal node files are not user inputs.", category="Dataset"),
    "dataset.crs": HelpTopic("dataset.crs", "Dataset CRS", "Coordinate reference system reported by the source metadata.", "Processing bounds, polygon overlays, and output placement depend on CRS alignment. Unknown CRS values should be reviewed before running clipped workflows.", category="Dataset"),
    "dataset.dimensions": HelpTopic("dataset.dimensions", "Point dimensions", "Available point attributes such as X, Y, Z, classification, and height-above-ground.", "Some products require specific dimensions or classifications. Missing dimensions may limit product availability or require preprocessing.", category="Dataset"),
    "planning.processing_crs": HelpTopic("planning.processing_crs", "Processing CRS", "CRS used for measurements, raster grids, and spatial reads.", "Use a projected CRS with metre-like units for area, resolution, and workload estimates. Avoid angular degrees for processing resolution.", category="Planning"),
    "planning.resolution": HelpTopic("planning.resolution", "Resolution", "Raster cell size for generated products.", "Choose a resolution compatible with point density. Very fine cells can create gaps, noisy surfaces, and longer runtimes.", category="Planning"),
    "planning.height_normalization": HelpTopic("planning.height_normalization", "Height normalization", "Converts point elevations into height above ground where products require it.", "CHM, PAD, PAI, FHD, and related products need a usable ground reference or HAG dimension. Defaults favor common classified LiDAR workflows.", category="Planning"),
    "processing.chm": HelpTopic("processing.chm", "Canopy Height Model", "Raster of vegetation height above the estimated ground surface.", "CHM requires a ground model or height-above-ground data. Resolution should reflect point density; too fine a grid can create unstable peaks or gaps.", category="Processing", keywords=("CHM",)),
    "processing.dtm": HelpTopic("processing.dtm", "Digital Terrain Model", "Raster representing estimated bare-earth elevation.", "DTM quality depends on ground-classified points or reliable ground filtering. It may be used as an intermediate for height normalization.", category="Processing"),
    "processing.canopy_cover": HelpTopic("processing.canopy_cover", "Canopy Cover", "Fraction or percent of each area occupied by canopy above a threshold.", "The height threshold changes interpretation. Keep the recommended value unless a project standard defines canopy differently.", category="Processing"),
    "processing.pad": HelpTopic("processing.pad", "Plant Area Density", "Vertical distribution of plant material across height bands.", "PAD is a multi-band output. Height-bin size and extinction settings affect scientific interpretation and should be changed deliberately.", category="Processing"),
    "processing.pai": HelpTopic("processing.pai", "Plant Area Index", "Estimated total plant area per unit ground area.", "PAI summarizes vertical structure into one raster. It inherits assumptions from PAD-style voxel and extinction settings.", category="Processing"),
    "processing.fhd": HelpTopic("processing.fhd", "Foliage Height Diversity", "Measure of how vegetation is distributed vertically.", "FHD is sensitive to vertical binning and missing understory returns. Use it comparatively across consistently processed data.", category="Processing"),
    "processing.rumple": HelpTopic("processing.rumple", "Rumple", "Canopy-surface roughness summary.", "A flat surface is near 1; more complex surfaces are higher. Treat scalar summaries as indicators, not complete structure descriptions.", category="Processing"),
    "processing.voxel_stat": HelpTopic("processing.voxel_stat", "Voxel Statistic", "Raster derived from 3D voxelized point statistics.", "Dimension and statistic choices change the meaning of the output. Advanced users should verify units and bin size.", category="Processing", applies_to_advanced=True),
    "batch.standard": HelpTopic("batch.standard", "Standard File Batch", "Runs selected products across a list of LAS/LAZ/COPC files.", "Use this for ordinary per-file processing. Polygon Area Processing is separate and clips work to an area of interest.", category="Batch"),
    "batch.polygon": HelpTopic("batch.polygon", "Polygon Area Processing", "Runs products for LiDAR intersecting a selected polygon.", "Mission Control queries the repository catalog, prepares a durable polygon job, and routes supported products through PBM when available.", category="Batch"),
    "batch.lidar_repository": HelpTopic("batch.lidar_repository", "LiDAR Repository", "Folder or ept.json containing LAS, LAZ, COPC, or EPT data.", "For EPT datasets, choose ept.json, the EPT root, or ept-data. Mission Control normalizes the selection to one logical EPT source.", documentation_anchor="docs/user-guide/polygon-folder-processing.md", category="Batch"),
    "batch.prepare_repository": HelpTopic("batch.prepare_repository", "Prepare Repository", "Creates or registers the spatial index needed for polygon queries.", "Automatic Setup uses the fastest trustworthy option. It avoids scanning EPT internals and uses built-in spatial access where possible.", documentation_anchor="docs/user-guide/choosing-lidar-index-strategy.md", category="Batch"),
    "batch.repository_setup_method": HelpTopic("batch.repository_setup_method", "Repository setup method", "Controls how Mission Control prepares spatial lookup for polygon processing.", "Leave this on Automatic Setup unless you already know the repository has a footprint index, EPT/COPC access, tile names, or folder regions.", common_mistake="Scanning file headers for a huge EPT repository is unnecessary and slow.", category="Batch", applies_to_advanced=True),
    "batch.catalog_location": HelpTopic("batch.catalog_location", "Catalog location", "Where the SQLite spatial catalog is stored.", "Network repositories use local PyForestScan application data by default. Move older repository-side catalogs local to reduce locking and latency.", category="Batch"),
    "batch.workload_estimate": HelpTopic("batch.workload_estimate", "Workload estimate", "A qualified estimate of processing size and uncertainty.", "EPT/COPC estimates are shown as unavailable unless the metadata supports a reliable polygon-subset estimate. This avoids false precision.", category="Batch"),
    "results.load_outputs": HelpTopic("results.load_outputs", "Load Outputs", "Adds generated rasters or tables to the current QGIS project.", "Mission Control avoids duplicate layers when possible. Large batch output folders should be loaded deliberately.", category="Results"),
    "advisor.recommendations": HelpTopic("advisor.recommendations", "Scientific Advisor", "Guidance based on dataset metadata and product prerequisites.", "Advisor output is supportive, not authoritative. Review project standards and field context before changing scientific parameters.", category="Scientific Advisor"),
    "environment.managed_backend": HelpTopic("environment.managed_backend", "Managed Backend", "User-local PBM environment used for routed processing.", "PBM does not modify QGIS Python or system Python. Repair or rebuild it from Settings when readiness checks fail.", category="Environment"),
    "environment.qgis_python": HelpTopic("environment.qgis_python", "QGIS Python fallback", "Optional fallback environment inside QGIS Python.", "Missing PyForestScan or PDAL in QGIS Python is not a blocker when PBM is Ready for routed products.", category="Environment"),
    "settings.performance": HelpTopic("settings.performance", "Performance settings", "Controls that can affect memory, runtime, and temporary storage.", "Recommended defaults are conservative. Increase concurrency only after confirming disk, network, and memory headroom.", category="Settings", applies_to_advanced=True),
    "settings.diagnostics": HelpTopic("settings.diagnostics", "Diagnostics", "Technical logs and paths used for troubleshooting.", "Diagnostics are useful after failures, but ordinary guided workflows should not require reading raw logs or JSON.", category="Settings", applies_to_advanced=True),
}


def get_help_topic(key: str) -> HelpTopic:
    """Return a registered topic or raise a useful KeyError."""
    try:
        return HELP_TOPICS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown Mission Control help topic: {key}") from exc


def help_topic_keys() -> tuple[str, ...]:
    return tuple(sorted(HELP_TOPICS))
