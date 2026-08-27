"""Lightweight UI availability and Mission Control lifecycle models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UiInitializationState(str, Enum):
    """Lifecycle states that gate late UI projections."""

    CREATING = "CREATING"
    READY = "READY"
    DESTROYING = "DESTROYING"


@dataclass(frozen=True)
class ApplicationAvailability:
    """Keep UI availability independent from scientific processing readiness."""

    ui_available: bool = True
    processing_available: bool = False
    engine_status: str = "CHECKING"
    message: str = "Processing Engine status is being checked."
    repair_required: bool = False

    @classmethod
    def from_engine(cls, engine: object) -> "ApplicationAvailability":
        status = str(getattr(getattr(engine, "status", None), "value", "FAILED"))
        return cls(
            ui_available=True,
            processing_available=bool(getattr(engine, "ready_for_processing", False)),
            engine_status=status,
            message=str(getattr(engine, "message", "Processing Engine status unavailable.")),
            repair_required=bool(getattr(engine, "repair_needed", False)),
        )

    @classmethod
    def unavailable(cls, message: str) -> "ApplicationAvailability":
        return cls(message=message, engine_status="FAILED")
