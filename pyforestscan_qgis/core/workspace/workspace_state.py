"""Workspace state and status models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class WorkspaceStatus(str, Enum):
    """High-level status for one analysis workspace."""

    DATASET_SELECTED = "dataset_selected"
    PLANNING_COMPLETE = "planning_complete"
    PRODUCTS_GENERATED = "products_generated"
    BATCH_COMPLETE = "batch_complete"
    QA_REVIEWED = "qa_reviewed"
    PUBLICATION_READY = "publication_ready"


@dataclass(frozen=True)
class WorkspaceState:
    """Current user-facing progress state for a workspace."""

    dataset_selected: bool = False
    planning_complete: bool = False
    products_generated: bool = False
    batch_complete: bool = False
    qa_reviewed: bool = False
    publication_ready: bool = False
    current_step: str = "Select dataset"
    completion_percentage: int = 0

    def with_status(self, status: WorkspaceStatus, value: bool = True, current_step: str | None = None) -> "WorkspaceState":
        """Return a new state with one status flag changed."""
        data = self.to_dict()
        data[status.value] = value
        if current_step is not None:
            data["current_step"] = current_step
        data["completion_percentage"] = _completion_percentage(data)
        return WorkspaceState.from_dict(data)

    def with_current_step(self, current_step: str) -> "WorkspaceState":
        """Return a new state with updated current step text."""
        return WorkspaceState(
            dataset_selected=self.dataset_selected,
            planning_complete=self.planning_complete,
            products_generated=self.products_generated,
            batch_complete=self.batch_complete,
            qa_reviewed=self.qa_reviewed,
            publication_ready=self.publication_ready,
            current_step=current_step,
            completion_percentage=self.completion_percentage,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable state."""
        return {
            "dataset_selected": self.dataset_selected,
            "planning_complete": self.planning_complete,
            "products_generated": self.products_generated,
            "batch_complete": self.batch_complete,
            "qa_reviewed": self.qa_reviewed,
            "publication_ready": self.publication_ready,
            "current_step": self.current_step,
            "completion_percentage": self.completion_percentage,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceState":
        """Build workspace state from JSON data."""
        return cls(
            dataset_selected=bool(payload.get("dataset_selected", False)),
            planning_complete=bool(payload.get("planning_complete", False)),
            products_generated=bool(payload.get("products_generated", False)),
            batch_complete=bool(payload.get("batch_complete", False)),
            qa_reviewed=bool(payload.get("qa_reviewed", False)),
            publication_ready=bool(payload.get("publication_ready", False)),
            current_step=str(payload.get("current_step") or "Select dataset"),
            completion_percentage=int(payload.get("completion_percentage", _completion_percentage(payload))),
        )


def _completion_percentage(payload: dict[str, Any]) -> int:
    flags = (
        "dataset_selected",
        "planning_complete",
        "products_generated",
        "batch_complete",
        "qa_reviewed",
        "publication_ready",
    )
    complete = sum(1 for flag in flags if bool(payload.get(flag, False)))
    return int(round((complete / len(flags)) * 100))
