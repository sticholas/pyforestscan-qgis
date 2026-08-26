"""Complete managed scientific runtime contract for advertised products."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_PYFORESTSCAN_VERSION = "0.4.1"

PYFORESTSCAN_FUNCTION_CONTRACT: dict[str, tuple[str, ...]] = {
    "pyforestscan": (
        "calculate_chm", "assign_voxels", "calculate_pad", "calculate_pai",
        "calculate_fhd", "calculate_rumple", "calculate_canopy_cover",
        "calculate_point_density", "calculate_voxel_stat", "generate_dtm",
    ),
    "pyforestscan.handlers": ("read_lidar", "create_geotiff", "write_las"),
    "pyforestscan.filters": (
        "classify_ground_points", "filter_select_ground", "remove_outliers_and_clean",
        "filter_ground", "filter_pointsourceid", "add_height_above_ground",
        "filter_hag", "downsample_poisson", "downsample_voxel",
    ),
    "pyforestscan.calculate": (),
    "pyforestscan.process": (),
}


@dataclass(frozen=True)
class DependencyContract:
    name: str
    import_name: str
    version_range: str
    products: tuple[str, ...]


ALL_PRODUCTS = ("chm", "rumple", "pad", "pai", "fhd", "canopy_cover", "dtm", "point_density", "voxel_stat")
PROCESSING_ENGINE_DEPENDENCIES = (
    DependencyContract("PyForestScan", "pyforestscan", "==0.4.1", ALL_PRODUCTS),
    DependencyContract("PDAL Python", "pdal", ">=3.4,<4", ALL_PRODUCTS),
    DependencyContract("Rasterio", "rasterio", ">=1.4,<1.5", ALL_PRODUCTS),
    DependencyContract("NumPy", "numpy", ">=1.26,<2", ALL_PRODUCTS),
    DependencyContract("GDAL", "osgeo.gdal", ">=3.9,<3.10", ALL_PRODUCTS),
    DependencyContract("SciPy", "scipy", ">=1.14,<2", ALL_PRODUCTS),
    DependencyContract("Shapely", "shapely", ">=2,<3", ALL_PRODUCTS),
    DependencyContract("PyProj", "pyproj", ">=3.7,<4", ALL_PRODUCTS),
    DependencyContract("pandas", "pandas", ">=2,<3", ("rumple", "pad", "pai", "fhd")),
)

PRODUCT_CAPABILITIES = {
    "chm": ("calculate_chm", "read_lidar", "create_geotiff"),
    "rumple": ("calculate_chm", "calculate_rumple", "read_lidar", "create_geotiff"),
    "pad": ("assign_voxels", "calculate_pad", "read_lidar", "create_geotiff"),
    "pai": ("assign_voxels", "calculate_pad", "calculate_pai", "read_lidar", "create_geotiff"),
    "fhd": ("assign_voxels", "calculate_fhd", "read_lidar", "create_geotiff"),
    "canopy_cover": ("assign_voxels", "calculate_pad", "calculate_canopy_cover", "read_lidar", "create_geotiff"),
    "dtm": ("generate_dtm", "read_lidar", "create_geotiff", "filter_select_ground"),
    "point_density": ("assign_voxels", "calculate_point_density", "read_lidar", "create_geotiff"),
    "voxel_stat": ("calculate_voxel_stat", "read_lidar", "create_geotiff"),
}
