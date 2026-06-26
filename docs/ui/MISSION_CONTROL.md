# Mission Control

Mission Control is the dockable graphical operating environment for PyForestScan
QGIS. It coordinates the workflows already implemented in the plugin while
leaving Processing algorithms available for advanced and automated use.

Mission Control does not call PyForestScan directly. It uses plugin core services
and the adapter boundary.

```mermaid
flowchart TD
    A["Mission Control dock"] --> B["UI pages"]
    B --> C["PyForestScanAdapter"]
    B --> W["RunContext"]
    W --> D["Dataset report core"]
    W --> E["Product planner core"]
    W --> H["Job manager"]
    H --> P["Pipeline registry"]
    C --> F["Dependency checks and dataset inspection"]
    H --> C
    C --> G["PyForestScan public API"]
```

## Pages

- Home: plugin version, PyForestScan version, environment status, latest dataset,
  latest project, recent activity, quick start, and documentation access.
- Environment: adapter-backed runtime checks for QGIS, Python, PyForestScan,
  PDAL, GDAL, rasterio, and numpy.
- Dataset: choose LAS, LAZ, COPC, or EPT plus an output folder, create the active
  run folder, and write Dataset Explorer reports into it.
- Planning: Product Planner uses the active Dataset Explorer report and writes
  plan reports into the run folder. No product execution is performed.
- Processing: start a CHM job from the active Product Planner report, view
  progress, inspect pipeline stages, write `outputs/chm.tif`, and write
  `logs/job_summary.json`.
- Results: view friendly Dataset Report, Product Plan, Job Summary, Output
  Folder, and Products links, with raw paths under Advanced details.
- Settings: default output folder, logging placeholder, and future preferences.

## UI Architecture

- `pyforestscan_qgis/ui/forms/mission_control.ui`: Qt Designer shell for the
  dock header, sidebar, page stack, and status bar.
- `pyforestscan_qgis/ui/mission_control.py`: dock controller and signal wiring.
- `pyforestscan_qgis/ui/pages.py`: modular page widgets.
- `pyforestscan_qgis/ui/state.py`: plain-Python immutable Mission Control state.
- `pyforestscan_qgis/core/workspace.py`: run-folder path model shared by Mission Control pages.

## Signal And Slot Architecture

```mermaid
flowchart LR
    A["Navigation list"] --> B["Stacked page index"]
    C["Environment refresh"] --> D["environmentChanged"]
    E["Dataset explored"] --> F["datasetExplored with RunContext"]
    F --> G["Planning and Processing receive active run"]
    H["Plan built"] --> I["planningChanged"]
    K["Job update"] --> L["jobUpdated"]
    D --> J["Status bar and Home"]
    F --> J
    I --> J
    L --> J
    L --> M["Results job history"]
```

## Scope Boundary

Mission Control coordinates current workflows only. The run folder is not a
required `.pfs` project file. The Processing page runs the active Product
Planner JSON through JobManager and the pipeline registry. CHM is implemented
through the adapter; PAI, PAD, FHD, canopy cover, and rumple remain future
products.
