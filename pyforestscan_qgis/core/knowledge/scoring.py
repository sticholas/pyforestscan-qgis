"""Transparent scoring helpers for knowledge reports."""

from __future__ import annotations

from .types import DatasetFacts, Recommendation, RecommendationSeverity


def dataset_score(recommendations: tuple[Recommendation, ...]) -> int:
    """Return a simple suitability score from recommendation severities."""
    score = 100
    for item in recommendations:
        if item.severity is RecommendationSeverity.ERROR:
            score -= 25
        elif item.severity is RecommendationSeverity.WARNING:
            score -= 10
    return max(0, min(100, score))


def confidence_stars(facts: DatasetFacts) -> int:
    """Return a metadata completeness confidence score from 0 to 5."""
    checks = (
        facts.point_count is not None,
        facts.estimated_density is not None,
        facts.area is not None,
        bool(facts.crs),
        bool(facts.dimensions),
        facts.has_classification_summary,
    )
    present = sum(1 for item in checks if item)
    return round((present / len(checks)) * 5)
