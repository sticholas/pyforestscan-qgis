"""Reusable contextual help controls for Mission Control."""

from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeyEvent
from qgis.PyQt.QtWidgets import QMessageBox, QToolButton, QWidget

from ..compat.qt import install_enum_aliases
from .help_topics import HelpTopic, get_help_topic

install_enum_aliases(Qt, "CursorShape", ("PointingHandCursor",))
install_enum_aliases(Qt, "FocusPolicy", ("StrongFocus",))
install_enum_aliases(Qt, "Key", ("Key_Enter", "Key_Return", "Key_Space"))

INFO_BADGE_STYLESHEET = """
QToolButton[infoBadge="true"] {
    color: #ffffff;
    background-color: #1976d2;
    border: 1px solid #0d47a1;
    border-radius: 8px;
    font-weight: 700;
    padding: 0px;
}
QToolButton[infoBadge="true"]:hover {
    background-color: #1e88e5;
    border-color: #0d47a1;
}
QToolButton[infoBadge="true"]:focus {
    border: 2px solid #64b5f6;
}
QToolButton[infoBadge="true"]:disabled {
    color: #6b7780;
    background-color: #dfe6e9;
    border-color: #b8c2c8;
}
"""


@dataclass(frozen=True)
class InfoHelpText:
    """Help text attached to one Mission Control control."""

    short_text: str
    detailed_text: str
    documentation_anchor: str | None = None
    warning_level: str = "info"
    accessible_name: str = "Information"
    key: str | None = None
    title: str = "Information"
    recommended_default: str = ""
    consequences: str = ""
    common_mistake: str = ""

    @classmethod
    def from_topic(cls, topic: HelpTopic) -> "InfoHelpText":
        return cls(
            short_text=topic.short_text,
            detailed_text=topic.detailed_text,
            documentation_anchor=topic.documentation_anchor,
            accessible_name=f"Help for {topic.title}",
            key=topic.key,
            title=topic.title,
            recommended_default=topic.recommended_default,
            consequences=topic.consequences,
            common_mistake=topic.common_mistake,
        )


class InfoBadge(QToolButton):
    """Small polished blue circular information badge with tooltip and detail dialog."""

    def __init__(self, help_text: InfoHelpText, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.help_text = help_text
        self.setText("i")
        self.setProperty("infoBadge", True)
        self.setProperty("help_topic_key", help_text.key or "custom")
        self.setStyleSheet(INFO_BADGE_STYLESHEET)
        self.setFixedSize(18, 18)
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(help_text.short_text)
        self.setAccessibleName(help_text.accessible_name or f"Help for {help_text.title}")
        self.setFocusPolicy(Qt.StrongFocus)
        self.clicked.connect(self.show_detail)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.show_detail()
            event.accept()
            return
        super().keyPressEvent(event)

    def show_detail(self) -> None:
        parts = [self.help_text.detailed_text]
        if self.help_text.recommended_default:
            parts.append(f"Recommended default: {self.help_text.recommended_default}")
        if self.help_text.consequences:
            parts.append(f"Consequence: {self.help_text.consequences}")
        if self.help_text.common_mistake:
            parts.append(f"Common mistake: {self.help_text.common_mistake}")
        if self.help_text.documentation_anchor:
            parts.append(f"Learn more: {self.help_text.documentation_anchor}")
        QMessageBox.information(self, self.help_text.title or self.accessibleName(), "\n\n".join(parts))


class InfoHelpButton(InfoBadge):
    """Backward-compatible name for existing Mission Control page code."""


def info_badge(topic_key: str, *, parent: QWidget | None = None) -> InfoBadge:
    """Create a standard information badge from the centralized topic registry."""
    return InfoBadge(InfoHelpText.from_topic(get_help_topic(topic_key)), parent=parent)


def info_help_button(short_text: str, detailed_text: str, *, accessible_name: str = "Information", documentation_anchor: str | None = None, parent: QWidget | None = None) -> InfoHelpButton:
    """Create a standard Mission Control information badge from inline text."""
    return InfoHelpButton(InfoHelpText(short_text, detailed_text, documentation_anchor=documentation_anchor, accessible_name=accessible_name, title=accessible_name), parent=parent)
