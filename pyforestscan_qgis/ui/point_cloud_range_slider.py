"""Small dual-handle range control for QGIS point-cloud selection."""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QPainter, QPen, QBrush
from qgis.PyQt.QtWidgets import QWidget
from ..compat.qt import qt_enum


class HeightRangeSlider(QWidget):
    valuesChanged = pyqtSignal(float, float)
    rangeCommitted = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0.0
        self._maximum = 1.0
        self._lower = 0.0
        self._upper = 1.0
        self._active = "lower"
        self._drag_offset = 0.0
        self.setMinimumHeight(26)
        self.setMinimumWidth(170)
        self.setFocusPolicy(qt_enum(Qt, "StrongFocus", "FocusPolicy"))
        self.setAccessibleName("Height selection range")
        self.setToolTip("Drag the handles to choose the inclusive vertical range. Keyboard arrows adjust the focused handle.")

    def setRange(self, minimum, maximum):
        minimum, maximum = float(minimum), float(maximum)
        if maximum <= minimum:
            maximum = minimum + 1.0
        self._minimum, self._maximum = minimum, maximum
        self.setValues(self._lower, self._upper, emit=False)

    def setValues(self, lower, upper, *, emit=True):
        lower = max(self._minimum, min(self._maximum, float(lower)))
        upper = max(self._minimum, min(self._maximum, float(upper)))
        if lower > upper:
            lower, upper = upper, lower
        self._lower, self._upper = lower, upper
        self.update()
        if emit:
            self.valuesChanged.emit(lower, upper)

    def values(self):
        return self._lower, self._upper

    def _track(self):
        return self.contentsRect().adjusted(10, 0, -10, 0)

    def _x_for(self, value):
        track = self._track()
        span = self._maximum - self._minimum
        return track.left() if span <= 0 else track.left() + (float(value) - self._minimum) / span * track.width()

    def _value_for(self, x):
        track = self._track()
        fraction = 0.0 if track.width() <= 0 else (float(x) - track.left()) / track.width()
        fraction = max(0.0, min(1.0, fraction))
        return self._minimum + fraction * (self._maximum - self._minimum)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = self._track()
        y = self.height() // 2
        painter.setPen(QPen(self.palette().mid(), 3))
        painter.drawLine(track.left(), y, track.right(), y)
        painter.setPen(QPen(self.palette().highlight(), 5))
        painter.drawLine(int(self._x_for(self._lower)), y, int(self._x_for(self._upper)), y)
        painter.setPen(QPen(self.palette().text(), 1))
        painter.setBrush(QBrush(self.palette().highlight()))
        for value in (self._lower, self._upper):
            painter.drawEllipse(int(self._x_for(value)) - 6, y - 6, 12, 12)

    def _choose_handle(self, x):
        lower_distance = abs(float(x) - self._x_for(self._lower))
        upper_distance = abs(float(x) - self._x_for(self._upper))
        self._active = "lower" if lower_distance <= upper_distance else "upper"

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.setFocus()
        self._choose_handle(event.position().x() if hasattr(event, "position") else event.x())
        self._drag_offset = 0.0
        self._set_from_x(event.position().x() if hasattr(event, "position") else event.x())
        event.accept()

    def mouseMoveEvent(self, event):
        if not event.buttons() & Qt.LeftButton:
            return
        self._set_from_x(event.position().x() if hasattr(event, "position") else event.x())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._set_from_x(event.position().x() if hasattr(event, "position") else event.x())
            self.rangeCommitted.emit(self._lower, self._upper)
        event.accept()

    def _set_from_x(self, x):
        value = self._value_for(x)
        if self._active == "lower":
            value = min(value, self._upper)
            self.setValues(value, self._upper)
        else:
            value = max(value, self._lower)
            self.setValues(self._lower, value)

    def keyPressEvent(self, event):
        step = (self._maximum - self._minimum) / 100.0
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.rangeCommitted.emit(self._lower, self._upper)
            event.accept()
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Down):
            step = -step
        elif event.key() not in (Qt.Key_Right, Qt.Key_Up):
            return super().keyPressEvent(event)
        if self._active == "lower":
            self.setValues(self._lower + step, self._upper)
        else:
            self.setValues(self._lower, self._upper + step)
        event.accept()
