"""State-derived progress for polygon processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"})


@dataclass
class PolygonProgressProjection:
    """Idempotently project ordered events without counting heartbeats as work."""

    total_datasets: int
    total_products: int
    last_sequence: int = -1
    last_heartbeat_sequence: int = -1
    datasets: dict[str, str] = field(default_factory=dict)
    products: dict[str, str] = field(default_factory=dict)
    current: dict[str, Any] = field(default_factory=dict)

    def apply(self, event: dict[str, Any]) -> bool:
        sequence = int(event.get("sequence", -1))
        if event.get("event_type") == "HEARTBEAT":
            heartbeat_sequence = int(event.get("heartbeat_sequence", -1))
            if heartbeat_sequence <= self.last_heartbeat_sequence:
                return False
            self.last_heartbeat_sequence = heartbeat_sequence
            self.current = dict(event)
            return True
        if sequence <= self.last_sequence:
            return False
        self.last_sequence = sequence
        self.current = dict(event)
        entity_id = str(event.get("entity_id", ""))
        state = str(event.get("state", "RUNNING")).upper()
        if entity_id and event.get("entity_type") == "dataset":
            self.datasets[entity_id] = state
        elif entity_id and event.get("entity_type") == "product":
            self.products[entity_id] = state
        return True

    @property
    def completed_datasets(self) -> int:
        return sum(state in TERMINAL_STATES for state in self.datasets.values())

    @property
    def completed_products(self) -> int:
        return sum(state in TERMINAL_STATES for state in self.products.values())

    def summary(self) -> str:
        return f"Datasets: {self.completed_datasets} / {self.total_datasets} complete; Products: {self.completed_products} / {self.total_products} complete"


def progress_event(*, attempt_id: str, sequence: int, event_type: str, stage: str, entity_type: str, entity_id: str, state: str = "RUNNING", **details: Any) -> dict[str, Any]:
    """Build the stable coordinator-to-UI event schema."""
    return {
        "attempt_id": attempt_id, "sequence": int(sequence),
        "event_id": f"{attempt_id}:{int(sequence)}", "event_type": event_type,
        "stage": stage, "entity_type": entity_type, "entity_id": entity_id,
        "state": state, **details,
    }
