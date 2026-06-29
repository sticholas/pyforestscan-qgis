"""Scientific Advisor UI support data and helper functions."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.jobs import JobRecord


@dataclass(frozen=True)
class ProductExplanation:
    """Plain-language explanation for a PyForestScan product."""

    product_id: str
    label: str
    measures: str
    use_when: str
    be_cautious_when: str
    qgis_inspection: str


@dataclass(frozen=True)
class QgisToolInstruction:
    """Instruction for using an existing QGIS tool from the Advisor."""

    tool_name: str
    how_to_open: str
    use_for: str


PRODUCT_EXPLANATIONS: tuple[ProductExplanation, ...] = (
    ProductExplanation(
        "chm",
        "Canopy Height Model (CHM)",
        "Top-of-canopy height above ground for each raster cell.",
        "Use it to inspect canopy height patterns, gaps, edge effects, and as a prerequisite for interpretation of canopy structure.",
        "Be cautious when HeightAboveGround is missing, ground classification is weak, CRS units are not projected, or point density is too low for the selected grid size.",
        "Use QGIS Layer Styling and Histogram to inspect value range; use Elevation Profile or 3D View for qualitative height checks.",
    ),
    ProductExplanation(
        "canopy_cover",
        "Canopy Cover",
        "Fractional or proportional canopy presence above a selected height threshold.",
        "Use it when canopy closure or gap patterns are the primary question.",
        "Be cautious when the canopy height threshold does not match the ecosystem or study definition of canopy.",
        "Use QGIS Histogram to confirm values are in the expected 0 to 1 range and Layer Styling to adjust grayscale contrast.",
    ),
    ProductExplanation(
        "pad",
        "Plant Area Density (PAD)",
        "Height-binned vertical plant area density represented as a multi-band raster stack.",
        "Use it to inspect vertical canopy structure and compare relative density across height bins.",
        "Be cautious when height-bin size is not scientifically justified or when interpreting bands without checking their vertical meaning.",
        "Use QGIS Symbology to inspect the default RGB 5/3/2 composite or switch to individual bands for height-bin review.",
    ),
    ProductExplanation(
        "pai",
        "Plant Area Index (PAI)",
        "Integrated plant area over height, summarized as a single raster surface.",
        "Use it for spatial patterns in total vertical vegetation amount.",
        "Be cautious when PAD prerequisites, height normalization, or Beer-Lambert assumptions are uncertain.",
        "Use QGIS Histogram and Raster Calculator to inspect ranges and compare with other structural layers.",
    ),
    ProductExplanation(
        "fhd",
        "Foliage Height Diversity (FHD)",
        "Vertical diversity of foliage or plant area distribution across height bins.",
        "Use it to compare structural diversity across space.",
        "Be cautious when height bins are poorly matched to canopy height or when sparse returns make diversity unstable.",
        "Use QGIS Layer Styling and Histogram to inspect the FHD raster; compare against PAD or CHM for context.",
    ),
    ProductExplanation(
        "rumple",
        "Rumple Index",
        "A scalar summary of canopy surface roughness/complexity derived from canopy geometry.",
        "Use it as a plot or area-level structural complexity indicator when the analysis extent is scientifically appropriate.",
        "Be cautious for very small extents, low-density data, or uncalibrated grid sizes; Phase 16A intentionally does not assert a universal minimum area threshold.",
        "Open the Rumple CSV summary and compare it with CHM in QGIS; use QGIS Layout Manager only after scientific QA is complete.",
    ),
)


QGIS_TOOL_INSTRUCTIONS: tuple[QgisToolInstruction, ...] = (
    QgisToolInstruction("Processing Toolbox", "Processing > Toolbox, or use the Advisor button when available.", "Run PyForestScan workflows and QGIS QA algorithms reproducibly."),
    QgisToolInstruction("Layer Styling / Symbology", "Select a layer, then open Layer Styling or Layer Properties > Symbology.", "Review grayscale ranges, PAD RGB band choices, and output appearance."),
    QgisToolInstruction("Raster Histogram", "Layer Properties > Histogram for the selected raster layer.", "Check value distributions and detect blank, all-zero, or outlier-heavy rasters."),
    QgisToolInstruction("Raster Calculator", "Raster > Raster Calculator.", "Create transparent QA masks or compare generated raster products."),
    QgisToolInstruction("Elevation Profile", "View > Elevation Profile where available in your QGIS version.", "Inspect height patterns along transects as qualitative QA."),
    QgisToolInstruction("3D View", "View > New 3D Map View.", "Inspect canopy/terrain context visually; do not treat it as quantitative validation."),
    QgisToolInstruction("Layout Manager", "Project > Layout Manager.", "Create map outputs after data QA and scientific interpretation are complete."),
)


def product_explanations_by_id() -> dict[str, ProductExplanation]:
    """Return product explanations keyed by stable product id."""
    return {item.product_id: item for item in PRODUCT_EXPLANATIONS}


def completed_products_from_job(job: JobRecord) -> tuple[str, ...]:
    """Return product ids with completed result artifacts in a job."""
    mapping = {
        "chm_geotiff": "chm",
        "canopy_cover_geotiff": "canopy_cover",
        "pad_geotiff": "pad",
        "pai_geotiff": "pai",
        "fhd_geotiff": "fhd",
        "rumple_csv": "rumple",
    }
    products: list[str] = []
    for result in job.results:
        product = mapping.get(result.result_type)
        if product and product not in products:
            products.append(product)
    return tuple(products)
