"""Top-level workspace model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workspace_history import WorkspaceHistory
from .workspace_notes import WorkspaceNotes
from .workspace_session import WorkspaceSession
from .workspace_state import WorkspaceState
from .workspace_timeline import WorkspaceTimelineEvent, utc_timestamp
from .workspace_version import WorkspaceVersion


@dataclass(frozen=True)
class WorkspaceRecentItem:
    """Recent workspace-related item."""

    item_type: str
    path: Path
    label: str
    timestamp: str

    @classmethod
    def create(cls, item_type: str, path: Path | str, label: str | None = None) -> "WorkspaceRecentItem":
        """Create a recent item from a path."""
        item_path = Path(path)
        return cls(item_type=item_type, path=item_path, label=label or item_path.name, timestamp=utc_timestamp())

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable recent item data."""
        return {
            "item_type": self.item_type,
            "path": str(self.path),
            "label": self.label,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceRecentItem":
        """Build a recent item from JSON data."""
        return cls(
            item_type=str(payload.get("item_type") or "item"),
            path=Path(str(payload.get("path") or ".")),
            label=str(payload.get("label") or payload.get("path") or "item"),
            timestamp=str(payload.get("timestamp") or utc_timestamp()),
        )


@dataclass(frozen=True)
class Workspace:
    """One local PyForestScan analysis workspace."""

    workspace_id: str
    name: str
    output_root: Path
    workspace_dir: Path
    state: WorkspaceState
    session: WorkspaceSession
    history: WorkspaceHistory
    timeline: tuple[WorkspaceTimelineEvent, ...]
    notes: WorkspaceNotes
    recent_items: tuple[WorkspaceRecentItem, ...]
    version: WorkspaceVersion
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, output_root: Path | str, name: str | None = None, version: WorkspaceVersion | None = None) -> "Workspace":
        """Create a new workspace model for an output root."""
        root = Path(output_root)
        now = utc_timestamp()
        workspace_name = name or root.name or "PyForestScan Workspace"
        return cls(
            workspace_id=f"pfs-workspace-{uuid.uuid4().hex[:12]}",
            name=workspace_name,
            output_root=root,
            workspace_dir=root / ".pyforestscan",
            state=WorkspaceState(),
            session=WorkspaceSession(last_output_folder=root),
            history=WorkspaceHistory(),
            timeline=(WorkspaceTimelineEvent.create("workspace_created", "Workspace created"),),
            notes=WorkspaceNotes(),
            recent_items=(WorkspaceRecentItem.create("workspace", root / ".pyforestscan", workspace_name),),
            version=version or WorkspaceVersion(),
            created_at=now,
            updated_at=now,
        )

    def with_state(self, state: WorkspaceState) -> "Workspace":
        """Return workspace with updated state."""
        return self._replace(state=state)

    def with_session(self, session: WorkspaceSession) -> "Workspace":
        """Return workspace with updated session."""
        return self._replace(session=session)

    def with_history(self, history: WorkspaceHistory) -> "Workspace":
        """Return workspace with updated history."""
        return self._replace(history=history)

    def with_timeline_event(self, event: WorkspaceTimelineEvent) -> "Workspace":
        """Return workspace with a timeline event appended."""
        return self._replace(timeline=self.timeline + (event,))

    def with_notes(self, notes: WorkspaceNotes) -> "Workspace":
        """Return workspace with updated notes."""
        return self._replace(notes=notes)

    def with_recent_item(self, item: WorkspaceRecentItem, limit: int = 10) -> "Workspace":
        """Return workspace with a recent item prepended and trimmed."""
        filtered = tuple(existing for existing in self.recent_items if not (existing.item_type == item.item_type and existing.path == item.path))
        return self._replace(recent_items=((item,) + filtered)[:limit])

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable workspace metadata."""
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "output_root": str(self.output_root),
            "workspace_dir": str(self.workspace_dir),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        session: WorkspaceSession,
        history: WorkspaceHistory,
        timeline: tuple[WorkspaceTimelineEvent, ...],
        notes: WorkspaceNotes,
        recent_items: tuple[WorkspaceRecentItem, ...],
        version: WorkspaceVersion,
    ) -> "Workspace":
        """Build a workspace from persisted component data."""
        output_root = Path(str(payload.get("output_root") or "."))
        workspace_dir = Path(str(payload.get("workspace_dir") or output_root / ".pyforestscan"))
        return cls(
            workspace_id=str(payload.get("workspace_id") or f"pfs-workspace-{uuid.uuid4().hex[:12]}"),
            name=str(payload.get("name") or output_root.name or "PyForestScan Workspace"),
            output_root=output_root,
            workspace_dir=workspace_dir,
            state=WorkspaceState.from_dict(payload.get("state") or {}),
            session=session,
            history=history,
            timeline=timeline,
            notes=notes,
            recent_items=recent_items,
            version=version,
            created_at=str(payload.get("created_at") or utc_timestamp()),
            updated_at=str(payload.get("updated_at") or utc_timestamp()),
        )

    def _replace(self, **changes: object) -> "Workspace":
        data = {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "output_root": self.output_root,
            "workspace_dir": self.workspace_dir,
            "state": self.state,
            "session": self.session,
            "history": self.history,
            "timeline": self.timeline,
            "notes": self.notes,
            "recent_items": self.recent_items,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": utc_timestamp(),
        }
        data.update(changes)
        return Workspace(**data)  # type: ignore[arg-type]
