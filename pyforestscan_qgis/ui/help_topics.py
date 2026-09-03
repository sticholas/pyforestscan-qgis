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
    "processing.rumple": HelpTopic("processing.rumple", "Rumple Index", "Dimensionless canopy-surface complexity raster.", "Flat surfaces are near 1 and more complex surfaces are higher. Upstream PyForestScan returns an area scalar; this spatial extension stores the same triangulated ratio for each valid 2x2 CHM patch. Values depend on CHM resolution, interpolation, minimum height, and NoData support.", category="Processing"),
    "processing.voxel_stat": HelpTopic("processing.voxel_stat", "Voxel Statistic", "Raster derived from 3D voxelized point statistics.", "Dimension and statistic choices change the meaning of the output. Advanced users should verify units and bin size.", category="Processing", applies_to_advanced=True),
    "batch.standard": HelpTopic("batch.standard", "LiDAR Folder Selection", "Runs selected products across a folder of LAS/LAZ/COPC files.", "Use this for ordinary per-file processing. Polygon Area Processing is separate and clips work to an area of interest.", category="Batch"),
    "batch.polygon": HelpTopic("batch.polygon", "Polygon Selection", "Runs products for LiDAR intersecting a selected polygon.", "Mission Control queries the repository catalog, prepares a durable polygon job, and routes supported products through PBM when available.", category="Batch"),
    "batch.lidar_repository": HelpTopic("batch.lidar_repository", "LiDAR Repository", "Folder or ept.json containing LAS, LAZ, COPC, or EPT data.", "For EPT datasets, choose ept.json, the EPT root, or ept-data. Mission Control normalizes the selection to one logical EPT source.", documentation_anchor="docs/user-guide/polygon-folder-processing.md", category="Batch"),
    "batch.prepare_repository": HelpTopic("batch.prepare_repository", "Prepare Repository", "Creates or registers the spatial index needed for polygon queries.", "Automatic Setup uses the fastest trustworthy option. It avoids scanning EPT internals and uses built-in spatial access where possible.", documentation_anchor="docs/user-guide/choosing-lidar-index-strategy.md", category="Batch"),
    "batch.repository_setup_method": HelpTopic("batch.repository_setup_method", "Repository setup method", "Controls how Mission Control prepares spatial lookup for polygon processing.", "Leave this on Automatic Setup unless you already know the repository has a footprint index, EPT/COPC access, tile names, or folder regions.", common_mistake="Scanning file headers for a huge EPT repository is unnecessary and slow.", category="Batch", applies_to_advanced=True),
    "batch.catalog_location": HelpTopic("batch.catalog_location", "Catalog location", "Where the SQLite spatial catalog is stored.", "Network repositories use local PyForestScan application data by default. Move older repository-side catalogs local to reduce locking and latency.", category="Batch"),
    "batch.workload_estimate": HelpTopic("batch.workload_estimate", "Workload estimate", "A qualified estimate of processing size and uncertainty.", "EPT/COPC estimates are shown as unavailable unless the metadata supports a reliable polygon-subset estimate. This avoids false precision.", category="Batch"),
    "batch.processing_concurrency": HelpTopic("batch.processing_concurrency", "Processing concurrency", "Guided control for how much Batch work may run at once.", "Sequential is safest. Parallel Safe mode uses guardrails and records both requested and effective concurrency in diagnostics.", category="Batch", applies_to_advanced=True),
    "batch.concurrent_jobs": HelpTopic("batch.concurrent_jobs", "Concurrent logical jobs", "Maximum independent jobs that Batch may schedule.", "EPT and COPC sources remain one logical spatial source. Concurrency applies across polygons or products, never internal hierarchy nodes.", category="Batch", applies_to_advanced=True),
    "batch.effective_concurrency": HelpTopic("batch.effective_concurrency", "Effective concurrency", "The actual concurrency after safety limits are applied.", "Mission Control may reduce a requested value for single EPT/COPC jobs, shared output paths, memory pressure, or source constraints.", category="Batch", applies_to_advanced=True),
    "batch.continue_on_error": HelpTopic("batch.continue_on_error", "Continue on error", "Whether independent items continue after a failure.", "Failures are recorded per logical job. A mask or load failure should not invalidate unrelated successful products.", category="Batch", applies_to_advanced=True),
    "batch.retry_failed_jobs": HelpTopic("batch.retry_failed_jobs", "Retry failed jobs", "Repeats failed logical attempts when resume data is available.", "Future retry actions distinguish product generation, mask finalization, and QGIS loading so valid expensive outputs are not regenerated unnecessarily.", category="Batch", applies_to_advanced=True),
    "batch.output_conflict_policy": HelpTopic("batch.output_conflict_policy", "Output conflict policy", "Controls whether existing outputs are skipped, reused, overwritten, or treated as conflicts.", "Polygon finalization follows the same shared output policy as Standard File Batch and never presents temporary unmasked rasters as final outputs.", category="Batch", applies_to_advanced=True),
    "batch.load_outputs_after_completion": HelpTopic("batch.load_outputs_after_completion", "Load outputs after completion", "Loads successful registered outputs into QGIS after finalization.", "For Polygon Area Processing, loading waits for exact masking and output registration. QGIS layer APIs run only from the UI side.", category="Batch", applies_to_advanced=True),
    "batch.exact_raster_mask": HelpTopic("batch.exact_raster_mask", "Exact raster mask", "Turns polygon-envelope rasters into final rasters with NoData outside the exact polygon.", "The GeoTIFF remains rectangular, but cells outside the selected Polygon or MultiPolygon become NoData and holes remain NoData.", category="Batch", applies_to_advanced=True),
    "batch.mask_implementation": HelpTopic("batch.mask_implementation", "Mask implementation", "Chooses Automatic, Managed Backend, or QGIS/GDAL mask finalization.", "Automatic prefers backend finalization for PBM-produced rasters and can use QGIS/GDAL Clip Raster by Mask Layer when selected or available as a recovery path.", category="Batch", applies_to_advanced=True),
    "batch.crop_to_polygon_extent": HelpTopic("batch.crop_to_polygon_extent", "Crop to polygon extent", "Crops the final raster grid to the polygon envelope while keeping NoData outside the exact geometry.", "Cropping reduces raster dimensions. It still does not create a physically nonrectangular raster file.", category="Batch", applies_to_advanced=True),
    "batch.include_touched_cells": HelpTopic("batch.include_touched_cells", "Include touched cells", "Includes raster cells touched by the polygon boundary during masking.", "Turning this on can include edge cells whose centers fall outside the polygon. Leave it off for stricter center-based masks.", category="Batch", applies_to_advanced=True),
    "batch.retain_unmasked_intermediate": HelpTopic("batch.retain_unmasked_intermediate", "Retain unmasked intermediate", "Keeps the rectangle-envelope raster for diagnostics.", "Retained intermediates are not registered as primary Results outputs and should not be loaded as final polygon products.", category="Batch", applies_to_advanced=True),
    "batch.mask_failure_policy": HelpTopic("batch.mask_failure_policy", "Mask failure policy", "Controls whether a generated polygon raster is considered failed if exact masking fails.", "The recommended setting fails the product so users are not shown an unmasked envelope raster as a successful polygon output.", category="Batch", applies_to_advanced=True),
    "results.generated_vs_loaded": HelpTopic("results.generated_vs_loaded", "Generated versus loaded", "Generated means the file exists and is registered; loaded means QGIS has added it as a layer.", "A QGIS loading failure does not delete or invalidate a generated product. Use Results to retry loading without regenerating products.", category="Results"),
    "results.load_outputs": HelpTopic("results.load_outputs", "Load Outputs", "Adds generated rasters or tables to the current QGIS project.", "Mission Control avoids duplicate layers when possible. Large batch output folders should be loaded deliberately.", category="Results"),
    "advisor.recommendations": HelpTopic("advisor.recommendations", "Scientific Advisor", "Guidance based on dataset metadata and product prerequisites.", "Advisor output is supportive, not authoritative. Review project standards and field context before changing scientific parameters.", category="Scientific Advisor"),
    "environment.managed_backend": HelpTopic("environment.managed_backend", "Managed Backend", "User-local PBM environment used for routed processing.", "PBM does not modify QGIS Python or system Python. Repair or rebuild it from Settings when readiness checks fail.", category="Environment"),
    "environment.qgis_python": HelpTopic("environment.qgis_python", "QGIS Python fallback", "Optional fallback environment inside QGIS Python.", "Missing PyForestScan or PDAL in QGIS Python is not a blocker when PBM is Ready for routed products.", category="Environment"),
    "settings.performance": HelpTopic("settings.performance", "Performance settings", "Controls that can affect memory, runtime, and temporary storage.", "Recommended defaults are conservative. Increase concurrency only after confirming disk, network, and memory headroom.", category="Settings", applies_to_advanced=True),
    "processing.validate_request": HelpTopic("processing.validate_request", "Validate Processing Request", "Checks backend API compatibility, EPT metadata, bounds syntax, polygon files, CRS, and output writability before products run.", "This fast gate should fail before point-cloud reading when a request is malformed. It does not generate CHM or other product outputs.", documentation_anchor="docs/user-guide/troubleshooting-processing-jobs.md", category="Processing"),
    "processing.test_spatial_read": HelpTopic("processing.test_spatial_read", "Test Spatial Read", "Troubleshooting-only bounded reader probe.", "Use this only when request validation passes but a real EPT reader still fails. It is separate from normal preflight because it touches the EPT source.", documentation_anchor="docs/user-guide/troubleshooting-processing-jobs.md", category="Processing", applies_to_advanced=True),
    "processing.diagnostic_test_run": HelpTopic("processing.diagnostic_test_run", "Diagnostic Test Run", "Runs validation and optional reader probing without full product generation.", "Diagnostic runs help isolate backend request issues before long production jobs.", documentation_anchor="docs/user-guide/troubleshooting-processing-jobs.md", category="Processing", applies_to_advanced=True),
    "results.export_diagnostics": HelpTopic("results.export_diagnostics", "Export Diagnostic Bundle", "Collects safe job diagnostics for support.", "Bundles include versions, request arguments, validation checks, progress events, and traceback details while avoiding credentials and full environment dumps.", documentation_anchor="docs/development/JOB_DIAGNOSTICS.md", category="Results"),
    "results.support_summary": HelpTopic("results.support_summary", "Copy Support Summary", "Creates a concise failure summary for issues or support chats.", "The summary includes product, failed stage, error code, request bounds, backend versions, and diagnostic path without secrets.", documentation_anchor="docs/user-guide/troubleshooting-processing-jobs.md", category="Results"),
    "settings.diagnostics": HelpTopic("settings.diagnostics", "Diagnostics", "Technical logs and paths used for troubleshooting.", "Diagnostics are useful after failures, but ordinary guided workflows should not require reading raw logs or JSON.", category="Settings", applies_to_advanced=True),
}


SEMANTIC_CONTEXT_HELP: dict[str, str] = {
    "process.folder.discover": "Scan the selected folder for supported LiDAR datasets and list them for processing. Source files are not modified.",
    "process.folder.select_all": "Select every discovered supported LiDAR dataset in this folder for the next processing request.",
    "process.folder.clear": "Clear the currently discovered LiDAR files from this processing selection. This does not delete or modify the source files.",
    "process.folder.search_subfolders": "Include supported LiDAR datasets found inside subfolders when discovering files.",
    "process.polygon.layer": "Choose the loaded QGIS polygon layer that defines the area to process. Selected features from this layer can be adopted as the processing area.",
    "process.polygon.use_selection": "Use the features currently selected on the QGIS map as the processing area. The original layer and features are not modified.",
    "process.polygon.refresh": "Refresh the polygon layers, current feature count, area, geometry validity, and CRS after the QGIS map selection changes.",
    "process.polygon.zoom": "Zoom the QGIS map canvas to the current processing area.",
    "product.chm": "Canopy Height Model: maximum height above ground within each horizontal output cell.",
    "product.canopy_cover": "Estimates canopy cover above a height threshold from PAD using the Beer-Lambert relation.",
    "product.pad": "Plant Area Density: estimates plant material density through vertical canopy layers.",
    "product.pai": "Plant Area Index: integrates Plant Area Density through a selected vertical height range.",
    "product.fhd": "Foliage Height Diversity: measures how LiDAR returns are distributed through vertical canopy layers.",
    "product.rumple": "Measures canopy-surface complexity as surface area relative to horizontal area.",
    "product.point_density": "Summarizes LiDAR return density over the output grid.",
    "product.voxel_stat": "Summarizes a selected point attribute within the three-dimensional voxel grid.",
    "product.dtm": "Digital Terrain Model: estimates ground-surface elevation.",
    "parameter.grid_resolution": "Horizontal output-cell size in source map units. Smaller cells preserve finer detail but increase processing time and raster size.",
    "parameter.voxel_height": "Vertical height of each voxel layer. Smaller layers preserve finer vertical structure but require more memory and processing time.",
    "parameter.canopy.threshold": "Lowest height above ground counted as canopy when estimating canopy cover.",
    "parameter.canopy.max_height": "Highest canopy layer included in canopy cover. Automatic uses the available vertical extent.",
    "parameter.canopy.extinction": "Controls conversion from integrated plant area to canopy cover in the Beer-Lambert relationship. PyForestScan defaults to 0.5.",
    "parameter.pad.beer_lambert": "Coefficient used by the Beer-Lambert transformation when estimating Plant Area Density.",
    "parameter.pad.drop_ground": "Exclude the lowest voxel layer from PAD so ground returns are not interpreted as plant material.",
    "parameter.pai.min_height": "Lowest height above ground included when integrating Plant Area Density into Plant Area Index.",
    "parameter.pai.max_height": "Highest height above ground included in PAI. Automatic uses the full available canopy height.",
    "parameter.fhd.min_height": "Lowest height above ground included in the FHD calculation. Returns below this threshold are excluded.",
    "parameter.fhd.max_height": "Highest height above ground included in FHD. Automatic uses the available canopy height.",
    "parameter.rumple.min_height": "Ignore canopy-height cells below this threshold when calculating surface complexity.",
    "parameter.point_density.per_area": "Divide return counts by horizontal cell area to report density per square source-map unit.",
    "parameter.chm.interpolation": "Controls how gaps between measured canopy-height cells are filled. Linear interpolation estimates values from nearby valid cells and is the PyForestScan default.",
    "parameter.restore_defaults": "Restore the supported PyForestScan scientific defaults without changing the selected data, products, or output folder.",
    "parameter.calculation_reference": "Open the official PyForestScan calculation reference for definitions, parameters, defaults, and calculation behavior.",
    "tools.fallback_crs": "Optional CRS to assume when a LiDAR dataset has no usable coordinate reference information. It never replaces a valid source CRS. Only set this when you know the coordinate system of otherwise unreferenced data.",
}


def semantic_help(key: str) -> str:
    """Return explicit contextual help; stable keys prevent placeholder prose."""
    try:
        return SEMANTIC_CONTEXT_HELP[key]
    except KeyError as exc:
        raise KeyError(f"Unknown semantic context-help key: {key}") from exc


SEMANTIC_ACTION_HELP: dict[str, str] = {
    "Browse": "Open a file or folder chooser for the adjacent path field. Choosing a path does not modify source data.",
    "Continue": "Move to the next ready step while preserving the selections already made on this page.",
    "Check Environment": "Check QGIS and the managed Processing Engine, then report whether routed products can run.",
    "Refresh Summary": "Re-read the current project, workspace, dataset, output, and Processing Engine state.",
    "Select Dataset": "Choose the LiDAR dataset Mission Control will inspect and use for the guided workflow.",
    "Open Backend Settings": "Open Processing Engine setup, verification, repair, and diagnostic controls.",
    "Open Processing Toolbox": "Open QGIS Processing Toolbox to the expert PyForestScan algorithms.",
    "Build Plan": "Validate selected products and parameters, then build the processing and output plan.",
    "Prerun Check": "Validate engine, source, area, coordinate systems, products, storage, and workload before dispatch.",
    "Set Up Processing Engine": "Install and verify the isolated user-local scientific runtime without modifying QGIS Python.",
    "Load into QGIS": "Add registered output rasters and supported tables to the current QGIS project without regenerating them.",
    "Open Output Folder": "Open the folder containing the current run's generated products and provenance files.",
    "Open Folder": "Open the current result folder in the desktop file manager.",
    "Refresh": "Re-read the nearby QGIS or filesystem state without changing source data.",
    "Recheck": "Run Processing Engine readiness verification again and update the displayed state.",
    "Open Diagnostics": "Show technical engine identity, verification, paths, and failure details for troubleshooting.",
    "Cancel Processing": "Request a controlled stop for remaining owned processing work; completed checkpoints are retained.",
    "Pause After Current Step": "Stop dispatching new work after active units finish so the durable job can be resumed.",
    "Clear Current Run": "Remove the current run from the Results view without deleting generated output files.",
    "New Run": "Clear the current result selection and prepare Mission Control for another processing request.",
}


def semantic_action_help(label: str) -> str:
    """Return explicit help for a reusable action label, or an empty string."""
    return SEMANTIC_ACTION_HELP.get(str(label).replace("&", "").strip(), "")


def get_help_topic(key: str) -> HelpTopic:
    """Return a registered topic or raise a useful KeyError."""
    try:
        return HELP_TOPICS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown Mission Control help topic: {key}") from exc


def help_topic_keys() -> tuple[str, ...]:
    return tuple(sorted(HELP_TOPICS))
