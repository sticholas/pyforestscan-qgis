"""Truthful scientific visualization contracts for point-cloud overlays."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

class ProductAvailability(str, Enum):
    AVAILABLE_CACHED = "AVAILABLE_CACHED"
    AVAILABLE_CAN_CALCULATE = "AVAILABLE_CAN_CALCULATE"
    CALCULATING = "CALCULATING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


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

    @property
    def scientific_support_geometry(self) -> str:
        return self.kind.value

    @property
    def value_domain(self) -> str:
        return {
            "CHM": "continuous height above ground",
            "DTM": "continuous source elevation",
            "CANOPY_COVER": "fraction 0-1",
            "PAD": "continuous per-height-bin plant area density",
            "PAI": "continuous plant area index",
            "FHD": "unitless entropy",
            "RUMPLE": "surface-area ratio",
            "POINT_DENSITY": "points per output cell area",
            "VOXEL_STATISTIC": "statistic-defined",
        }.get(self.product_id, "product-defined")

    @property
    def legend_type(self) -> str:
        return "categorical" if self.kind is VisualizationKind.VERTICAL_PROFILE else "continuous"

@dataclass(frozen=True)
class ScientificVisualizationState:
    spec: ScientificVisualizationSpec
    availability: ProductAvailability
    reason: str
    layer: "ScientificVisualizationLayer" | None = None


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
    ("CANOPY_COVER", "Canopy Cover", VisualizationKind.RASTER_SURFACE, "fraction 0-1", "height-threshold canopy occupancy", "Viridis", "Canopy occupancy fraction above the configured threshold."),
    ("PAD", "Plant Area Density", VisualizationKind.VOXEL_FIELD, "area per volume", "height-bin distribution", "Forest", "Multi-band height-binned plant area density; band semantics come from provenance."),
    ("PAI", "Plant Area Index", VisualizationKind.RASTER_SURFACE, "area per area", "height-integrated vegetation", "Viridis", "Height-integrated plant area index raster."),
    ("FHD", "Foliage Height Diversity", VisualizationKind.RASTER_SURFACE, "unitless entropy", "height-bin diversity", "CoolWarm", "Spatial foliage-height diversity raster."),
    ("RUMPLE", "Rumple Index", VisualizationKind.SCALAR_PATCH, "dimensionless ratio", "canopy surface complexity", "Terrain", "Localized canopy-surface complexity derived from a CHM."),
    ("POINT_DENSITY", "Point Density", VisualizationKind.RASTER_SURFACE, "points per output cell area", "source elevation support", "Viridis", "Point-count density over output cells."),
    ("VOXEL_STATISTIC", "Voxel Statistic", VisualizationKind.VOXEL_FIELD, "product-defined units", "configured voxel statistic", "Viridis", "A statistic over configured 3D voxel bins."),
)
SPECS = {row[0]: ScientificVisualizationSpec(row[0], row[1], row[2], row[3], row[4], row[5], (".tif", ".tiff"), row[6]) for row in _ROWS}

def product_visualization_spec(product_id: str) -> ScientificVisualizationSpec:
    key = str(product_id or "").strip().upper().replace(" ", "_")
    try:
        return SPECS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown scientific visualization product: {product_id}") from exc

def product_visualization_state(product_id: str, *, output_path: str | Path | None = None, can_calculate: bool = False, calculating: bool = False, review_required: bool = False, reason: str = "") -> ScientificVisualizationState:
    """Describe availability without starting calculation or inventing values."""
    spec = product_visualization_spec(product_id)
    if calculating:
        status = ProductAvailability.CALCULATING
        default_reason = "A managed calculation is in progress."
    elif output_path is not None and Path(output_path).is_file():
        status = ProductAvailability.AVAILABLE_CACHED
        default_reason = "A verified product output is available for visualization."
    elif review_required:
        status = ProductAvailability.REVIEW_REQUIRED
        default_reason = "The output exists or is planned but its spatial support needs review."
    elif can_calculate:
        status = ProductAvailability.AVAILABLE_CAN_CALCULATE
        default_reason = "The product can be calculated for the current scope by the managed engine."
    else:
        status = ProductAvailability.NOT_AVAILABLE
        default_reason = "No verified output or supported calculation path is available."
    return ScientificVisualizationState(spec, status, reason or default_reason)


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
