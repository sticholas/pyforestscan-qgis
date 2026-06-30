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
    GLOBAL_RECENT_WORKSPACES_FILE,
    WorkspaceManager,
)
from .workspace_display import RecentWorkspaceSummary, format_timeline_events, summarize_recent_workspaces, workspace_primary_action, workspace_status_label
from .workspace_notes import WorkspaceNotes
from .workspace_session import WorkspaceSession
from .workspace_state import WorkspaceState, WorkspaceStatus
from .workspace_timeline import WorkspaceTimelineEvent
from .workspace_version import CURRENT_WORKSPACE_FORMAT_VERSION, WorkspaceVersion

__all__ = [
    "CURRENT_WORKSPACE_FORMAT_VERSION",
    "GLOBAL_RECENT_WORKSPACES_FILE",
    "HISTORY_FILE",
    "NOTES_FILE",
    "RECENT_FILE",
    "RunContext",
    "SESSION_FILE",
    "TIMELINE_FILE",
    "VERSION_FILE",
    "WORKSPACE_FILE",
    "WORKSPACE_FOLDER_NAME",
    "RecentWorkspaceSummary",
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
    "format_timeline_events",
    "summarize_recent_workspaces",
    "workspace_primary_action",
    "workspace_status_label",
]
