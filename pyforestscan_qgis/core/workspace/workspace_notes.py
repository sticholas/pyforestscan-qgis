"""Workspace markdown notes model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceNotes:
    """Markdown notes stored with a workspace."""

    markdown: str = "# Workspace Notes\n\n"

    def with_markdown(self, markdown: str) -> "WorkspaceNotes":
        """Return updated notes."""
        return WorkspaceNotes(markdown=markdown)
