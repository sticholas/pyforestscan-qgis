"""Deterministic scientific-knowledge rules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .diagnostics import is_geographic_crs
from .messages import CALIBRATION_REQUIRED, FUTURE_DOCUMENTATION_LINK, HEIGHT_NORMALIZATION_NOTE, PROJECTED_CRS_NOTE
from .types import (
    DatasetFacts,
    KnowledgeConfig,
    QgisToolSuggestion,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    RecommendedParameter,
    RecommendedProduct,
)


@dataclass(frozen=True)
class RuleResult:
    """Output from one deterministic rule."""

    recommendations: tuple[Recommendation, ...] = ()
    parameters: tuple[RecommendedParameter, ...] = ()
    products: tuple[RecommendedProduct, ...] = ()
    qgis_tools: tuple[QgisToolSuggestion, ...] = ()


@dataclass(frozen=True)
class KnowledgeRule:
    """Registered deterministic rule."""

    rule_id: str
    description: str
    evaluate: Callable[[DatasetFacts, KnowledgeConfig], RuleResult]


def product_feasibility_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Translate Dataset Explorer product feasibility into product recommendations."""
    products: list[RecommendedProduct] = []
    for item in facts.supported_products:
        product = str(item.get("product", "unknown"))
        status = str(item.get("status", "Unknown"))
        label = str(item.get("label", product))
        reason = str(item.get("reason", "Dataset Explorer did not provide a reason."))
        normalized = {"Available": "recommended", "Warning": "needs_review", "Unavailable": "not_recommended"}.get(status, "needs_review")
        confidence = 4 if status == "Available" else 3 if status == "Warning" else 2
        products.append(RecommendedProduct(product=product, label=label, status=normalized, reason=reason, confidence=confidence))
    return RuleResult(products=tuple(products))


def density_resolution_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Recommend CHM grid resolution from configurable density thresholds."""
    density = facts.estimated_density
    if density is None:
        return RuleResult(recommendations=(
            Recommendation(
                code="DENSITY_UNKNOWN",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.PARAMETER,
                reason="Estimated point density is unavailable, so CHM grid-size guidance cannot be evaluated.",
                suggested_action="Inspect density from PDAL/QGIS metadata or run Dataset Explorer on a source that reports point count and bounds.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=2,
                product="chm",
                scientific_note="Resolution guidance depends on acquisition density and should not be guessed silently.",
            ),
        ))

    high = config.high_density_points_per_square_unit.value
    low = config.low_density_points_per_square_unit.value
    if high is not None and density >= high:
        value = config.fine_chm_resolution.value
        return RuleResult(parameters=(
            RecommendedParameter(
                product="chm",
                name="grid_resolution",
                value=value,
                unit=config.fine_chm_resolution.unit,
                reason=(
                    f"Estimated density {density:g} is at or above the configured high-density threshold "
                    f"{high:g}; a finer CHM grid may be scientifically defensible after local validation. {CALIBRATION_REQUIRED}"
                ),
                confidence=3,
                threshold_names=(config.high_density_points_per_square_unit.name, config.fine_chm_resolution.name),
                calibration_required=True,
            ),
        ))
    if low is not None and density < low:
        value = config.conservative_chm_resolution.value
        return RuleResult(parameters=(
            RecommendedParameter(
                product="chm",
                name="grid_resolution",
                value=value,
                unit=config.conservative_chm_resolution.unit,
                reason=(
                    f"Estimated density {density:g} is below the configured low-density threshold {low:g}; "
                    f"avoid over-interpreting sub-meter CHM cells. {CALIBRATION_REQUIRED}"
                ),
                confidence=3,
                threshold_names=(config.low_density_points_per_square_unit.name, config.conservative_chm_resolution.name),
                calibration_required=True,
            ),
        ))
    return RuleResult(parameters=(
        RecommendedParameter(
            product="chm",
            name="grid_resolution",
            value=config.conservative_chm_resolution.value,
            unit=config.conservative_chm_resolution.unit,
            reason=(
                f"Estimated density {density:g} falls between configured low and high thresholds; "
                "use a conservative starting grid and validate against project objectives."
            ),
            confidence=3,
            threshold_names=(config.low_density_points_per_square_unit.name, config.high_density_points_per_square_unit.name),
            calibration_required=True,
        ),
    ))


def height_readiness_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Warn when height-above-ground prerequisites are incomplete."""
    if facts.has_hag:
        return RuleResult(recommendations=(
            Recommendation(
                code="HAG_PRESENT",
                severity=RecommendationSeverity.INFO,
                category=RecommendationCategory.HEIGHT,
                reason="HeightAboveGround is present in the inspected dimensions.",
                suggested_action="Review height values during QA before treating normalized products as final.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=4,
            ),
        ))
    if facts.has_z:
        return RuleResult(recommendations=(
            Recommendation(
                code="HAG_MISSING",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.HEIGHT,
                reason=HEIGHT_NORMALIZATION_NOTE,
                suggested_action="Normalize heights using ground classification or a DTM before interpreting CHM, PAD, PAI, FHD, canopy cover, or rumple outputs.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=4,
            ),
        ))
    return RuleResult(recommendations=(
        Recommendation(
            code="HEIGHT_DIMENSION_MISSING",
            severity=RecommendationSeverity.ERROR,
            category=RecommendationCategory.HEIGHT,
            reason="Neither HeightAboveGround nor Z was reported by Dataset Explorer.",
            suggested_action="Inspect the source point cloud and confirm it includes usable height coordinates before processing.",
            documentation_link=FUTURE_DOCUMENTATION_LINK,
            confidence=4,
        ),
    ))


def classification_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Evaluate ground and vegetation classification availability."""
    recommendations: list[Recommendation] = []
    if not facts.has_classification_summary:
        recommendations.append(Recommendation(
            code="CLASSIFICATION_SUMMARY_MISSING",
            severity=RecommendationSeverity.WARNING,
            category=RecommendationCategory.CLASSIFICATION,
            reason="Dataset Explorer did not report classification counts.",
            suggested_action="Run a full or sampled classification inspection before relying on vegetation and ground-class assumptions.",
            documentation_link=FUTURE_DOCUMENTATION_LINK,
            confidence=3,
        ))
    else:
        if not facts.has_ground:
            recommendations.append(Recommendation(
                code="GROUND_CLASS_MISSING",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.CLASSIFICATION,
                reason="ASPRS ground class 2 was not detected in the classification summary.",
                suggested_action="Consider PDAL ground classification or an external DTM before height normalization.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=4,
            ))
        if not facts.has_vegetation:
            recommendations.append(Recommendation(
                code="VEGETATION_CLASSES_MISSING",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.CLASSIFICATION,
                reason="ASPRS vegetation classes 3, 4, and 5 were not detected.",
                suggested_action="Confirm classification scheme before interpreting vegetation-specific products.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=4,
            ))
    return RuleResult(recommendations=tuple(recommendations))


def crs_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Evaluate CRS suitability for raster metrics."""
    if not facts.crs:
        return RuleResult(recommendations=(
            Recommendation(
                code="CRS_UNKNOWN",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.CRS,
                reason="Dataset Explorer did not report a coordinate reference system.",
                suggested_action="Assign or confirm CRS before generating raster metrics.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=4,
            ),
        ))
    if is_geographic_crs(facts.crs):
        return RuleResult(recommendations=(
            Recommendation(
                code="CRS_GEOGRAPHIC",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.CRS,
                reason=PROJECTED_CRS_NOTE,
                suggested_action="Use a projected CRS appropriate for the study area before interpreting raster cell sizes and areas.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=3,
            ),
        ))
    return RuleResult()


def rumple_area_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Evaluate rumple-area guidance only when a project threshold is configured."""
    threshold = config.minimum_rumple_area
    if threshold.value is None:
        return RuleResult(recommendations=(
            Recommendation(
                code="RUMPLE_AREA_THRESHOLD_UNCONFIGURED",
                severity=RecommendationSeverity.INFO,
                category=RecommendationCategory.SCIENTIFIC_NOTE,
                reason="No default minimum area threshold is asserted for rumple stability.",
                suggested_action="Configure a project-specific threshold after calibration or literature review if rumple will be used for small extents.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=2,
                product="rumple",
                scientific_note=threshold.rationale,
                calibration_required=True,
            ),
        ))
    if facts.area is not None and facts.area < threshold.value:
        return RuleResult(recommendations=(
            Recommendation(
                code="RUMPLE_AREA_BELOW_CONFIGURED_THRESHOLD",
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.DATASET_SUITABILITY,
                reason=f"Dataset area {facts.area:g} is below the configured rumple area threshold {threshold.value:g}.",
                suggested_action="Treat rumple results as unstable or aggregate a larger area before interpretation.",
                documentation_link=FUTURE_DOCUMENTATION_LINK,
                confidence=3,
                product="rumple",
                calibration_required=threshold.calibration_required,
            ),
        ))
    return RuleResult()


def qgis_tools_rule(facts: DatasetFacts, config: KnowledgeConfig) -> RuleResult:
    """Suggest existing QGIS tools that support QA and interpretation."""
    tools = [
        QgisToolSuggestion("Processing Toolbox", "Run Dataset Explorer, Product Planner, and product workflows reproducibly.", "Use before and after each production run."),
        QgisToolSuggestion("Layer Styling", "Inspect raster symbology, display range, and PAD band assignments.", "Use after generated rasters are loaded."),
        QgisToolSuggestion("Histogram", "Check whether raster values and display ranges are plausible.", "Use during QA for CHM, canopy cover, PAI, PAD, and FHD."),
        QgisToolSuggestion("Elevation Profile", "Inspect vertical structure where QGIS supports profile workflows.", "Use when validating height patterns against terrain and canopy expectations."),
        QgisToolSuggestion("3D View", "Visually inspect canopy height and terrain context.", "Use as qualitative QA, not as a substitute for quantitative validation."),
        QgisToolSuggestion("Layout Manager", "Prepare reproducible map outputs after scientific QA is complete.", "Use for communication and publication figures."),
    ]
    return RuleResult(qgis_tools=tuple(tools))
