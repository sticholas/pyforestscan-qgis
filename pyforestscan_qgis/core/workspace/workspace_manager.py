"""Local workspace persistence manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .workspace import Workspace, WorkspaceRecentItem
from .workspace_history import WorkspaceHistory, WorkspaceHistoryRun
from .workspace_notes import WorkspaceNotes
from .workspace_session import WorkspaceSession
from .workspace_state import WorkspaceState, WorkspaceStatus
from .workspace_timeline import WorkspaceTimelineEvent
from .workspace_version import WorkspaceVersion

WORKSPACE_FOLDER_NAME = ".pyforestscan"
WORKSPACE_FILE = "workspace.json"
SESSION_FILE = "session.json"
TIMELINE_FILE = "timeline.json"
NOTES_FILE = "notes.md"
HISTORY_FILE = "history.json"
RECENT_FILE = "recent.json"
VERSION_FILE = "version.json"
GLOBAL_SESSION_FILE = "session.json"


class WorkspaceManager:
    """Create, load, and auto-save local PyForestScan workspaces."""

    def __init__(self, config_root: Path | str | None = None, recent_limit: int = 10, auto_save: bool = True) -> None:
        """Create a manager with optional global session root."""
        self.config_root = Path(config_root) if config_root is not None else Path.home() / ".pyforestscan_qgis"
        self.recent_limit = recent_limit
        self.auto_save = auto_save

    def workspace_dir(self, output_root: Path | str) -> Path:
        """Return the hidden workspace folder for an output root."""
        return Path(output_root) / WORKSPACE_FOLDER_NAME

    def create_workspace(self, output_root: Path | str, name: str | None = None) -> Workspace:
        """Create and persist a workspace for an output root."""
        workspace = Workspace.create(output_root, name=name)
        return self.save_workspace(workspace) if self.auto_save else workspace

    def load_workspace(self, output_root: Path | str) -> Workspace:
        """Load a workspace, creating it when no metadata exists."""
        root = Path(output_root)
        folder = self.workspace_dir(root)
        metadata_path = folder / WORKSPACE_FILE
        if not metadata_path.exists():
            return self.create_workspace(root)
        metadata = _read_json(metadata_path)
        workspace = Workspace.from_dict(
            metadata,
            session=WorkspaceSession.from_dict(_read_json(folder / SESSION_FILE, default={})),
            history=WorkspaceHistory.from_dict(_read_json(folder / HISTORY_FILE, default={})),
            timeline=tuple(WorkspaceTimelineEvent.from_dict(item) for item in _read_json(folder / TIMELINE_FILE, default={"events": []}).get("events", [])),
            notes=WorkspaceNotes((folder / NOTES_FILE).read_text(encoding="utf-8") if (folder / NOTES_FILE).exists() else WorkspaceNotes().markdown),
            recent_items=tuple(WorkspaceRecentItem.from_dict(item) for item in _read_json(folder / RECENT_FILE, default={"items": []}).get("items", [])),
            version=WorkspaceVersion.from_dict(_read_json(folder / VERSION_FILE, default={})),
        )
        return workspace

    def save_workspace(self, workspace: Workspace) -> Workspace:
        """Persist all workspace component files and return the workspace."""
        workspace.workspace_dir.mkdir(parents=True, exist_ok=True)
        _write_json(workspace.workspace_dir / WORKSPACE_FILE, workspace.to_dict())
        _write_json(workspace.workspace_dir / SESSION_FILE, workspace.session.to_dict())
        _write_json(workspace.workspace_dir / TIMELINE_FILE, {"events": [event.to_dict() for event in workspace.timeline]})
        (workspace.workspace_dir / NOTES_FILE).write_text(workspace.notes.markdown, encoding="utf-8")
        _write_json(workspace.workspace_dir / HISTORY_FILE, workspace.history.to_dict())
        _write_json(workspace.workspace_dir / RECENT_FILE, {"items": [item.to_dict() for item in workspace.recent_items]})
        _write_json(workspace.workspace_dir / VERSION_FILE, workspace.version.to_dict())
        return workspace

    def update_state(self, workspace: Workspace, status: WorkspaceStatus, value: bool = True, current_step: str | None = None) -> Workspace:
        """Update workspace status and auto-save."""
        updated = workspace.with_state(workspace.state.with_status(status, value, current_step))
        return self.save_workspace(updated) if self.auto_save else updated

    def add_timeline_event(self, workspace: Workspace, event_type: str, message: str, details: dict[str, str] | None = None) -> Workspace:
        """Append a timeline event and auto-save."""
        updated = workspace.with_timeline_event(WorkspaceTimelineEvent.create(event_type, message, details))
        return self.save_workspace(updated) if self.auto_save else updated

    def append_history(self, workspace: Workspace, run: WorkspaceHistoryRun) -> Workspace:
        """Append processing history and auto-save."""
        updated = workspace.with_history(workspace.history.append(run))
        return self.save_workspace(updated) if self.auto_save else updated

    def add_recent_item(self, workspace: Workspace, item_type: str, path: Path | str, label: str | None = None) -> Workspace:
        """Record a recent workspace item and auto-save."""
        item = WorkspaceRecentItem.create(item_type, path, label)
        updated = workspace.with_recent_item(item, limit=max(1, self.recent_limit))
        return self.save_workspace(updated) if self.auto_save else updated

    def save_global_session(self, session: WorkspaceSession) -> Path:
        """Persist the cross-workspace Mission Control session pointer."""
        self.config_root.mkdir(parents=True, exist_ok=True)
        path = self.config_root / GLOBAL_SESSION_FILE
        _write_json(path, session.to_dict())
        return path

    def load_global_session(self) -> WorkspaceSession:
        """Load the cross-workspace Mission Control session pointer."""
        path = self.config_root / GLOBAL_SESSION_FILE
        if not path.exists():
            return WorkspaceSession()
        return WorkspaceSession.from_dict(_read_json(path, default={}))


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default or {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Workspace file is not valid JSON: {path}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
