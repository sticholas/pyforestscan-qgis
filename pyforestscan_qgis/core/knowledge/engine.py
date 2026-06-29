"""Deterministic Knowledge Engine entry points."""

from __future__ import annotations

from typing import Any, Mapping

from .diagnostics import facts_from_dataset_explorer_report
from .recommendation import RecommendationReport
from .registry import default_rule_registry
from .rules import KnowledgeRule
from .scoring import confidence_stars, dataset_score
from .types import DatasetFacts, KnowledgeConfig, QgisToolSuggestion, Recommendation, RecommendedParameter, RecommendedProduct


class KnowledgeEngine:
    """Evaluate Dataset Explorer facts with deterministic documented rules."""

    def __init__(self, config: KnowledgeConfig | None = None, rules: tuple[KnowledgeRule, ...] | None = None) -> None:
        """Create a knowledge engine with configurable thresholds and rules."""
        self.config = config or KnowledgeConfig()
        self.rules = rules or default_rule_registry()

    def evaluate_facts(self, facts: DatasetFacts) -> RecommendationReport:
        """Evaluate normalized dataset facts and return a typed report."""
        recommendations: list[Recommendation] = []
        products: list[RecommendedProduct] = []
        parameters: list[RecommendedParameter] = []
        qgis_tools: list[QgisToolSuggestion] = []
        for rule in self.rules:
            result = rule.evaluate(facts, self.config)
            recommendations.extend(result.recommendations)
            products.extend(result.products)
            parameters.extend(result.parameters)
            qgis_tools.extend(result.qgis_tools)

        recommendation_tuple = tuple(recommendations)
        return RecommendationReport(
            dataset_score=dataset_score(recommendation_tuple),
            confidence_stars=confidence_stars(facts),
            recommended_products=tuple(products),
            recommended_parameters=tuple(parameters),
            warnings=tuple(item for item in recommendation_tuple if item.severity.value in {"warning", "error"}),
            suggested_next_actions=tuple(item for item in recommendation_tuple if item.category.value == "next_action"),
            scientific_notes=tuple(item for item in recommendation_tuple if item.scientific_note or item.category.value == "scientific_note"),
            qgis_tool_suggestions=tuple(qgis_tools),
            thresholds=self.config.thresholds(),
        )

    def evaluate_dataset_explorer_report(self, report: Mapping[str, Any]) -> RecommendationReport:
        """Evaluate a Dataset Explorer JSON dictionary."""
        return self.evaluate_facts(facts_from_dataset_explorer_report(report))


def evaluate_dataset_explorer_report(
    report: Mapping[str, Any],
    config: KnowledgeConfig | None = None,
) -> RecommendationReport:
    """Evaluate a Dataset Explorer report with the default Knowledge Engine."""
    return KnowledgeEngine(config=config).evaluate_dataset_explorer_report(report)
