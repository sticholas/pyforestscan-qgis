"""Non-destructive CRS registration for previously source-local rasters."""

from __future__ import annotations

import shutil
from pathlib import Path

from .spatial_reference_resolver import normalize_crs


def register_raster_crs_copy(source: Path | str, output: Path | str, crs: str, *, assignment_scope: str = "file") -> Path:
    """Copy a raster and attach confirmed CRS metadata without changing pixels/transform."""
    source_path = Path(source)
    output_path = Path(output)
    normalized = normalize_crs(crs)
    if not normalized:
        raise ValueError("A valid confirmed coordinate system is required.")
    if source_path.resolve() == output_path.resolve():
        raise ValueError("Choose a separate output so the original source-local product is preserved.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, output_path)
    try:
        import rasterio
        with rasterio.open(output_path, "r+") as dataset:
            dataset.crs = normalized
            dataset.update_tags(
                SOURCE_CRS_STATUS="USER_ASSIGNED",
                SOURCE_CRS=normalized,
                CRS_ASSIGNED="true",
                CRS_ASSIGNMENT_SCOPE=assignment_scope,
                TRANSFORMATION_APPLIED="false",
                ORIGINAL_SOURCE_LOCAL_PRODUCT=str(source_path),
            )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return output_path


__all__ = ["register_raster_crs_copy"]
