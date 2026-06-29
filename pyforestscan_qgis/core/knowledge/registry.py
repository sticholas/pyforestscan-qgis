"""Knowledge rule registry."""

from __future__ import annotations

from .rules import (
    KnowledgeRule,
    classification_rule,
    crs_rule,
    density_resolution_rule,
    height_readiness_rule,
    product_feasibility_rule,
    qgis_tools_rule,
    rumple_area_rule,
)


def default_rule_registry() -> tuple[KnowledgeRule, ...]:
    """Return the default deterministic rule registry."""
    return (
        KnowledgeRule("product_feasibility", "Translate Dataset Explorer product feasibility.", product_feasibility_rule),
        KnowledgeRule("density_resolution", "Suggest CHM resolution from configurable density thresholds.", density_resolution_rule),
        KnowledgeRule("height_readiness", "Evaluate height-above-ground readiness.", height_readiness_rule),
        KnowledgeRule("classification", "Evaluate ground and vegetation classification availability.", classification_rule),
        KnowledgeRule("crs", "Evaluate CRS suitability for raster metrics.", crs_rule),
        KnowledgeRule("rumple_area", "Evaluate rumple area threshold only when configured.", rumple_area_rule),
        KnowledgeRule("qgis_tools", "Suggest QGIS QA and interpretation tools.", qgis_tools_rule),
    )
