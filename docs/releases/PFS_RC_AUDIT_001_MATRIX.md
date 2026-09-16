# PFS-RC-AUDIT-001 Feature Matrix

Source inventory from `processing_provider.py`; QGIS-dependent execution is marked explicitly in the qualification manifest.

| Feature | Surface | Module | Status | QGIS runtime |
| --- | --- | --- | --- | --- |
| EnvironmentCheckAlgorithm (`environment_check`) | Processing Toolbox | `pyforestscan_qgis/algorithms/placeholder_algorithms.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedChmAlgorithm (`advanced_chm`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_chm.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedPadAlgorithm (`advanced_pad`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_pad.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| PadDerivativeRasterAlgorithm (`pad_derivative_raster`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/pad_derivative.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedPaiAlgorithm (`advanced_pai`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_pai.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedCanopyCoverAlgorithm (`advanced_canopy_cover`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_canopy_cover.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedFhdAlgorithm (`advanced_fhd`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_fhd.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedRumpleAlgorithm (`advanced_rumple`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_rumple.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedPointDensityAlgorithm (`advanced_point_density`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_point_density.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedVoxelStatAlgorithm (`advanced_voxel_statistic`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_voxel_stat.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| NormalizeHagAlgorithm (`normalize_height_above_ground`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/normalize_hag.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| EptSubsetExtractAlgorithm (`extract_ept_subset`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/ept_subset.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| AdvancedDtmAlgorithm (`advanced_dtm`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/advanced_dtm.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |
| PointCloudPreprocessAlgorithm (`advanced_point_cloud_preprocess`) | Processing Toolbox | `pyforestscan_qgis/algorithms/advanced/point_cloud_preprocess.py` | PASS | UNQUALIFIED_QGIS_RUNTIME |

## Mission Control products

| Product | Folder / polygon contract | Status |
| --- | --- | --- |
| CHM | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| DTM | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| PAD | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| PAI | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| FHD | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| Canopy Cover | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| Rumple | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| Point Density | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |
| Voxel Statistic | Mission Control product registry and shared processing contracts | PASS (QGIS-independent) |

## Qualification boundary

The current Linux audit environment has no `qgis` Python module. Clean-profile installation, provider boot, algorithm construction through QgsProcessing, and live QGIS GUI execution therefore remain BLOCKED until run under the target QGIS runtime.
