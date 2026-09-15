"""Truthful scientific visualization contracts for point-cloud overlays."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

class VisualizationKind(str, Enum):
    RASTER_SURFACE = "raster_surface"
    VERTICAL_PROFILE = "vertical_profile"
    VOXEL_FIELD = "voxel_field"
    SCALAR_PATCH = "scalar_patch"

@dataclass(frozen=True)
class ScientificVisualizationSpec:
    product_id: str
    label: str
    kind: VisualizationKind
    units: str
    vertical_semantics: str
    palette: str
    output_suffixes: tuple[str, ...]
    description: str

@dataclass(frozen=True)
class ScientificVisualizationLayer:
    spec: ScientificVisualizationSpec
    output_path: str
    source_path: str
    source_fingerprint: str
    crs: str = ""
    resolution: tuple[float, float] | None = None
    value_range: tuple[float, float] | None = None
    nodata: float | None = None
    provenance: Mapping[str, str] = None

_ROWS = (
    ("CHM", "Canopy Height Model", VisualizationKind.RASTER_SURFACE, "source height units", "height above ground", "Forest", "Surface height above the prepared ground reference."),
    ("DTM", "Digital Terrain Model", VisualizationKind.RASTER_SURFACE, "source elevation units", "source elevation", "Terrain", "Bare-earth elevation surface."),
    ("CANOPY_COVER", "Canopy Cover", VisualizationKind.RASTER_SURFACE, "fraction or percent", "height-threshold canopy occupancy", "Viridis", "Canopy occupancy using the configured threshold."),
    ("PAD", "Plant Area Density", VisualizationKind.VOXEL_FIELD, "plant area density", "height-bin distribution", "Forest", "Vertical plant-area distribution; band semantics come from provenance."),
    ("PAI", "Plant Area Index", VisualizationKind.RASTER_SURFACE, "plant area index", "height-integrated vegetation", "Viridis", "Height-integrated plant area index."),
    ("FHD", "Foliage Height Diversity", VisualizationKind.RASTER_SURFACE, "diversity index", "height-bin diversity", "CoolWarm", "Vertical foliage-height diversity."),
    ("RUMPLE", "Rumple Index", VisualizationKind.SCALAR_PATCH, "dimensionless ratio", "canopy surface complexity", "Terrain", "Localized canopy-surface complexity derived from a CHM."),
    ("POINT_DENSITY", "Point Density", VisualizationKind.RASTER_SURFACE, "points per area", "source elevation support", "Viridis", "Point-count density over output cells."),
    ("VOXEL_STATISTIC", "Voxel Statistic", VisualizationKind.VOXEL_FIELD, "product-defined units", "configured voxel statistic", "Viridis", "A statistic over configured 3D voxel bins."),
)
SPECS = {row[0]: ScientificVisualizationSpec(row[0], row[1], row[2], row[3], row[4], row[5], (".tif", ".tiff"), row[6]) for row in _ROWS}

def product_visualization_spec(product_id: str) -> ScientificVisualizationSpec:
    key = str(product_id or "").strip().upper().replace(" ", "_")
    try:
        return SPECS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown scientific visualization product: {product_id}") from exc

def available_product_visualizations(outputs: Mapping[str, str | Path] | Sequence[str | Path]):
    """Return products whose supported output actually exists on disk."""
    if isinstance(outputs, Mapping):
        paths = {str(key).upper().replace(" ", "_"): Path(value) for key, value in outputs.items()}
    else:
        paths = {}
        for value in outputs:
            path = Path(value)
            stem = path.stem.upper().replace("-", "_").replace(" ", "_")
            for product_id, spec in SPECS.items():
                if path.suffix.lower() in spec.output_suffixes and product_id in stem:
                    paths[product_id] = path
    return tuple(spec for product_id, spec in SPECS.items() if paths.get(product_id) and paths[product_id].is_file())

def build_visualization_layer(product_id: str, *, output_path: str | Path, source_path: str | Path, source_fingerprint: str, crs: str = "", resolution=None, value_range=None, nodata=None, provenance=None):
    """Build a provenance-carrying descriptor for an existing product output."""
    output = Path(output_path)
    if not output.is_file():
        raise FileNotFoundError(f"Scientific visualization output does not exist: {output}")
    return ScientificVisualizationLayer(product_visualization_spec(product_id), str(output), str(source_path), str(source_fingerprint), str(crs or ""), resolution, value_range, nodata, dict(provenance or {}))
