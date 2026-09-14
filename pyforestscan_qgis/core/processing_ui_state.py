"""Authoritative processing-workspace state and control policy."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProcessingUiState(str, Enum):
    IDLE = "idle"
    VALIDATING = "validating"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    COMPLETE_WITH_WARNING = "complete_with_warning"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    RECOVERABLE = "recoverable"


ACTIVE_PROCESSING_STATES = frozenset({
    ProcessingUiState.VALIDATING,
    ProcessingUiState.STARTING,
    ProcessingUiState.RUNNING,
    ProcessingUiState.PAUSED,
    ProcessingUiState.FINALIZING,
})
TERMINAL_PROCESSING_STATES = frozenset({
    ProcessingUiState.COMPLETE,
    ProcessingUiState.COMPLETE_WITH_WARNING,
    ProcessingUiState.FAILED,
    ProcessingUiState.CANCELLED,
    ProcessingUiState.INTERRUPTED,
    ProcessingUiState.RECOVERABLE,
})


@dataclass(frozen=True)
class ProcessingControlPolicy:
    run_inputs_enabled: bool
    process_enabled: bool
    cancel_enabled: bool
    pause_enabled: bool
    diagnostics_enabled: bool


def control_policy(state: ProcessingUiState, *, ready_to_process: bool = True) -> ProcessingControlPolicy:
    """Return the complete control policy for one processing state."""
    active = state in ACTIVE_PROCESSING_STATES
    return ProcessingControlPolicy(
        run_inputs_enabled=not active,
        process_enabled=(not active and ready_to_process),
        cancel_enabled=state in {ProcessingUiState.STARTING, ProcessingUiState.RUNNING, ProcessingUiState.PAUSED},
        pause_enabled=state in {ProcessingUiState.RUNNING, ProcessingUiState.PAUSED},
        diagnostics_enabled=state is not ProcessingUiState.IDLE,
    )


def terminal_state_from_result(*, failed: int = 0, cancelled: bool = False, interrupted: bool = False, warning: bool = False) -> ProcessingUiState:
    if cancelled:
        return ProcessingUiState.CANCELLED
    if interrupted:
        return ProcessingUiState.INTERRUPTED
    if failed:
        return ProcessingUiState.FAILED
    return ProcessingUiState.COMPLETE_WITH_WARNING if warning else ProcessingUiState.COMPLETE


def reconcile_ui_state(ui_state: ProcessingUiState, durable_state: str | None, *, coordinator_active: bool) -> ProcessingUiState:
    """Repair a stale active UI projection from durable terminal state."""
    if ui_state not in ACTIVE_PROCESSING_STATES or coordinator_active:
        return ui_state
    normalized = str(durable_state or "").strip().lower()
    return {
        "complete": ProcessingUiState.COMPLETE,
        "completed": ProcessingUiState.COMPLETE,
        "complete_with_warning": ProcessingUiState.COMPLETE_WITH_WARNING,
        "failed": ProcessingUiState.FAILED,
        "scientific_blocker": ProcessingUiState.FAILED,
        "cancelled": ProcessingUiState.CANCELLED,
        "interrupted": ProcessingUiState.INTERRUPTED,
        "recoverable": ProcessingUiState.RECOVERABLE,
    }.get(normalized, ProcessingUiState.INTERRUPTED)


__all__ = ["ACTIVE_PROCESSING_STATES", "TERMINAL_PROCESSING_STATES", "ProcessingControlPolicy", "ProcessingUiState", "control_policy", "reconcile_ui_state", "terminal_state_from_result"]
