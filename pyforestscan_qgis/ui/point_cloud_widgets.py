"""Fixed-footprint help for an embedded rendering surface."""
from qgis.PyQt.QtWidgets import QPlainTextEdit, QSizePolicy, QLabel
from qgis.PyQt.QtCore import Qt
from ..compat.qt import qt_enum


class StableViewerStatus(QLabel):
    """One compact line; complete text remains available to hover/accessibility."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(qt_enum(QSizePolicy, "Ignored", "Policy"),
                           qt_enum(QSizePolicy, "Fixed", "Policy"))
        self.setFixedHeight(self.fontMetrics().height() + 6)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self.setAccessibleDescription(self._full_text)
        self._render()

    def _render(self):
        super().setText(self.fontMetrics().elidedText(self._full_text,
            qt_enum(Qt, "ElideRight", "TextElideMode"), max(1, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()


class StableViewerHelp(QPlainTextEdit):
    DEFAULT_TEXT = "Hover over or focus a control for more information."
    HEIGHT = 48

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAccessibleName("Point Cloud context help")
        self.setFixedHeight(self.HEIGHT)
        self.setMinimumWidth(0)
        self.setSizePolicy(qt_enum(QSizePolicy, "Ignored", "Policy"),
                           qt_enum(QSizePolicy, "Fixed", "Policy"))
        self.setHorizontalScrollBarPolicy(qt_enum(Qt, "ScrollBarAlwaysOff", "ScrollBarPolicy"))
        self.setLineWrapMode(qt_enum(QPlainTextEdit, "WidgetWidth", "LineWrapMode"))
        self.set_help()

    def set_help(self, text=None):
        value = (text or self.DEFAULT_TEXT).strip()
        self.setPlainText("Help | " + value)
        self.setToolTip(value)
        self.verticalScrollBar().setValue(0)
