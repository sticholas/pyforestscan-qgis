"""Recommendation report serialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import KnowledgeThreshold, QgisToolSuggestion, Recommendation, RecommendedParameter, RecommendedProduct


@dataclass(frozen=True)
class RecommendationReport:
    """Structured deterministic output from the Knowledge Engine."""

    dataset_score: int
    confidence_stars: int
    recommended_products: tuple[RecommendedProduct, ...]
    recommended_parameters: tuple[RecommendedParameter, ...]
    warnings: tuple[Recommendation, ...]
    suggested_next_actions: tuple[Recommendation, ...]
    scientific_notes: tuple[Recommendation, ...]
    qgis_tool_suggestions: tuple[QgisToolSuggestion, ...]
    thresholds: tuple[KnowledgeThreshold, ...]


def report_to_dict(report: RecommendationReport) -> dict[str, Any]:
    """Convert a recommendation report to JSON-serializable dictionaries."""
    return {
        "dataset_score": report.dataset_score,
        "confidence_stars": report.confidence_stars,
        "recommended_products": [product.__dict__ for product in report.recommended_products],
        "recommended_parameters": [parameter.__dict__ for parameter in report.recommended_parameters],
        "warnings": [_recommendation_to_dict(item) for item in report.warnings],
        "suggested_next_actions": [_recommendation_to_dict(item) for item in report.suggested_next_actions],
        "scientific_notes": [_recommendation_to_dict(item) for item in report.scientific_notes],
        "qgis_tool_suggestions": [tool.__dict__ for tool in report.qgis_tool_suggestions],
        "thresholds": [threshold.__dict__ for threshold in report.thresholds],
    }


def _recommendation_to_dict(item: Recommendation) -> dict[str, Any]:
    payload = dict(item.__dict__)
    payload["severity"] = item.severity.value
    payload["category"] = item.category.value
    return payload
