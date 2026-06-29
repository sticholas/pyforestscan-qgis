"""Deterministic knowledge engine for PyForestScan QGIS."""

from .engine import KnowledgeEngine, evaluate_dataset_explorer_report
from .recommendation import RecommendationReport, report_to_dict
from .types import (
    DatasetFacts,
    KnowledgeConfig,
    KnowledgeThreshold,
    QgisToolSuggestion,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    RecommendedParameter,
    RecommendedProduct,
)

__all__ = [
    "DatasetFacts",
    "KnowledgeConfig",
    "KnowledgeEngine",
    "KnowledgeThreshold",
    "QgisToolSuggestion",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationReport",
    "RecommendationSeverity",
    "RecommendedParameter",
    "RecommendedProduct",
    "evaluate_dataset_explorer_report",
    "report_to_dict",
]
