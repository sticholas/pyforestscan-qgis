"""Presentation helpers for workspace UI surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .workspace import Workspace
from .workspace_timeline import WorkspaceTimelineEvent


@dataclass(frozen=True)
class RecentWorkspaceSummary:
    """Display-safe recent workspace entry."""

    path: Path
    label: str
    exists: bool


def workspace_status_label(workspace: Workspace | None) -> str:
    """Return a concise user-facing workspace status label."""
    if workspace is None:
        return "No workspace open"
    state = workspace.state
    return f"{workspace.name}: {state.current_step} ({state.completion_percentage}% complete)"


def workspace_primary_action(workspace: Workspace | None) -> str:
    """Return the next useful action for Home and Workspace pages."""
    if workspace is None:
        return "Start a new workspace or continue a recent workspace."
    state = workspace.state
    if not state.dataset_selected:
        return "Select a LiDAR dataset."
    if not state.planning_complete:
        return "Build a Product Plan."
    if not state.products_generated and not state.batch_complete:
        return "Run selected products or start a batch."
    if not state.qa_reviewed:
        return "Review outputs in QGIS and inspect the job summary."
    if not state.publication_ready:
        return "Prepare publication-ready layouts or export materials."
    return "Workspace is publication ready."


def format_timeline_events(events: tuple[WorkspaceTimelineEvent, ...], limit: int = 10) -> tuple[str, ...]:
    """Format recent timeline events in reverse chronological order."""
    selected = tuple(reversed(events))[: max(0, limit)]
    return tuple(f"{_event_label(event.event_type)} - {event.message} ({event.timestamp})" for event in selected)


def summarize_recent_workspaces(paths: tuple[Path, ...], limit: int = 10) -> tuple[RecentWorkspaceSummary, ...]:
    """Return display summaries for recent workspace folders."""
    summaries: list[RecentWorkspaceSummary] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = raw_path
        if path in seen:
            continue
        seen.add(path)
        root = path.parent if path.name == ".pyforestscan" else path
        label = root.name or str(root)
        summaries.append(RecentWorkspaceSummary(path=path, label=label, exists=path.exists()))
        if len(summaries) >= limit:
            break
    return tuple(summaries)


def _event_label(event_type: str) -> str:
    labels = {
        "workspace_created": "Workspace created",
        "environment_refreshed": "Environment refreshed",
        "dataset_selected": "Dataset selected",
        "dataset_explored": "Dataset explored",
        "planning_updated": "Planning updated",
        "products_generated": "Products generated",
        "processing_failed": "Processing failed",
        "batch_complete": "Batch complete",
        "notes_saved": "Notes saved",
        "workspace_reset": "Workspace reset",
    }
    return labels.get(event_type, event_type.replace("_", " ").title())
