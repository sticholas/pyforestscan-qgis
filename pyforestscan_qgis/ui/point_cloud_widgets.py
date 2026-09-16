"""Fixed-footprint help for an embedded rendering surface."""
from qgis.PyQt.QtWidgets import QPlainTextEdit, QSizePolicy, QLabel
from qgis.PyQt.QtCore import Qt, QTimer
from ..compat.qt import qt_enum


class StableViewerStatus(QLabel):
    """One compact line; complete text remains available to hover/accessibility."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text
        self._busy = False
        self._busy_frame = 0
        self._spinner = QTimer(self)
        self._spinner.setInterval(120)
        self._spinner.timeout.connect(self._advance_spinner)
        self.setSizePolicy(qt_enum(QSizePolicy, "Ignored", "Policy"),
                           qt_enum(QSizePolicy, "Fixed", "Policy"))
        self.setFixedHeight(self.fontMetrics().height() + 6)
        self.setText(text)

    def setBusy(self, busy):
        """Show a small animation while a user-visible background job is active."""
        busy = bool(busy)
        if self._busy == busy:
            return
        self._busy = busy
        if busy:
            self._spinner.start()
        else:
            self._spinner.stop()
            self._busy_frame = 0
        self._render()

    def _advance_spinner(self):
        self._busy_frame = (self._busy_frame + 1) % 4
        self._render()

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self.setAccessibleDescription(self._full_text)
        self._render()

    def _render(self):
        prefix = ("Working " + ("|", "/", "-", "\\")[self._busy_frame] + " | ") if self._busy else ""
        super().setText(self.fontMetrics().elidedText(prefix + self._full_text,
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
