"""Workspace foundation package for PyForestScan QGIS."""

from .run_context import RunContext, create_run_context
from .workspace import Workspace, WorkspaceRecentItem
from .workspace_history import WorkspaceHistory, WorkspaceHistoryRun
from .workspace_manager import (
    HISTORY_FILE,
    NOTES_FILE,
    RECENT_FILE,
    SESSION_FILE,
    TIMELINE_FILE,
    VERSION_FILE,
    WORKSPACE_FILE,
    WORKSPACE_FOLDER_NAME,
    WorkspaceManager,
)
from .workspace_notes import WorkspaceNotes
from .workspace_session import WorkspaceSession
from .workspace_state import WorkspaceState, WorkspaceStatus
from .workspace_timeline import WorkspaceTimelineEvent
from .workspace_version import CURRENT_WORKSPACE_FORMAT_VERSION, WorkspaceVersion

__all__ = [
    "CURRENT_WORKSPACE_FORMAT_VERSION",
    "HISTORY_FILE",
    "NOTES_FILE",
    "RECENT_FILE",
    "RunContext",
    "SESSION_FILE",
    "TIMELINE_FILE",
    "VERSION_FILE",
    "WORKSPACE_FILE",
    "WORKSPACE_FOLDER_NAME",
    "Workspace",
    "WorkspaceHistory",
    "WorkspaceHistoryRun",
    "WorkspaceManager",
    "WorkspaceNotes",
    "WorkspaceRecentItem",
    "WorkspaceSession",
    "WorkspaceState",
    "WorkspaceStatus",
    "WorkspaceTimelineEvent",
    "WorkspaceVersion",
    "create_run_context",
]
