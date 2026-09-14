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
    last_progress_percent: int = 0
    active_attempt_id: str = ""

    def apply(self, event: dict[str, Any]) -> bool:
        attempt_id = str(event.get("attempt_id", ""))
        if self.active_attempt_id and attempt_id and attempt_id != self.active_attempt_id:
            return False
        if attempt_id and not self.active_attempt_id:
            self.active_attempt_id = attempt_id
        sequence = int(event.get("sequence", -1))
        if event.get("event_type") == "HEARTBEAT":
            heartbeat_sequence = int(event.get("heartbeat_sequence", -1))
            if heartbeat_sequence <= self.last_heartbeat_sequence:
                return False
            self.last_heartbeat_sequence = heartbeat_sequence
            # Heartbeats carry liveness only. Preserve the latest scientific
            # stage/product/region so a timer cannot regress the Processing UI.
            self.current = {**self.current, "process_alive": True, "last_seen": event.get("last_seen") or event.get("timestamp")}
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

    def progress_percent(self, event: dict[str, Any]) -> int:
        """Return a determinate, monotonic percentage for every polygon event.

        Coordinators provide precise progress when they can.  Older workers and
        setup stages do not, so derive a conservative estimate from terminal
        product work and the current stage instead of switching the UI to an
        indeterminate marquee.
        """
        raw = event.get("progress_percent")
        if isinstance(raw, (int, float)):
            self.last_progress_percent = max(self.last_progress_percent, max(0, min(99, int(raw))))
            return self.last_progress_percent
        total_work = max(1, self.total_datasets * max(1, self.total_products))
        completed = min(total_work, self.completed_products)
        exact = int((completed / total_work) * 100)
        stage = str(event.get("active_stage") or event.get("stage") or "").upper()
        stage_floor = {
            "STARTING": 1, "QUEUED": 1, "PREFLIGHT": 3, "VALIDATING": 5,
            "PREPARING": 8, "READING": 15, "NORMALIZING": 25,
            "GENERATING": 40, "PROCESSING": 45, "WRITING": 80,
            "MASKING": 90, "FINALIZING": 96,
        }
        estimate = stage_floor.get(stage, 1)
        # A non-terminal product is underway, so show progress through its
        # slice without claiming it completed.
        if self.current.get("entity_type") == "product" and completed < total_work:
            estimate = max(estimate, int(((completed + 0.35) / total_work) * 100))
        self.last_progress_percent = max(self.last_progress_percent, max(0, min(99, max(exact, estimate))))
        return self.last_progress_percent


def progress_event(*, attempt_id: str, sequence: int, event_type: str, stage: str, entity_type: str, entity_id: str, state: str = "RUNNING", **details: Any) -> dict[str, Any]:
    """Build the stable coordinator-to-UI event schema."""
    return {
        "attempt_id": attempt_id, "sequence": int(sequence),
        "event_id": f"{attempt_id}:{int(sequence)}", "event_type": event_type,
        "stage": stage, "entity_type": entity_type, "entity_id": entity_id,
        "state": state, **details,
    }
