"""Reusable contextual help controls for Mission Control."""

from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox, QToolButton, QWidget


@dataclass(frozen=True)
class InfoHelpText:
    """Help text attached to one Mission Control control."""

    short_text: str
    detailed_text: str
    documentation_anchor: str | None = None
    warning_level: str = "info"
    accessible_name: str = "Information"


class InfoHelpButton(QToolButton):
    """Small keyboard-accessible information button with tooltip and detail dialog."""

    def __init__(self, help_text: InfoHelpText, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.help_text = help_text
        self.setText("i")
        self.setToolTip(help_text.short_text)
        self.setAccessibleName(help_text.accessible_name or "Information")
        self.setFocusPolicy(Qt.StrongFocus)
        self.clicked.connect(self.show_detail)

    def show_detail(self) -> None:
        detail = self.help_text.detailed_text
        if self.help_text.documentation_anchor:
            detail = f"{detail}\n\nDocumentation: {self.help_text.documentation_anchor}"
        QMessageBox.information(self, self.accessibleName(), detail)


def info_help_button(short_text: str, detailed_text: str, *, accessible_name: str = "Information", documentation_anchor: str | None = None, parent: QWidget | None = None) -> InfoHelpButton:
    """Create a standard Mission Control information button."""
    return InfoHelpButton(InfoHelpText(short_text, detailed_text, documentation_anchor=documentation_anchor, accessible_name=accessible_name), parent=parent)
