"""Compact QGIS-theme tools; no additional selection or editing state."""
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize, pyqtSignal
from qgis.PyQt.QtWidgets import (QWidget, QHBoxLayout, QToolButton, QButtonGroup,
                                 QLabel, QDoubleSpinBox)


def spatial_button(label, icon, help_text, parent=None):
    button = QToolButton(parent)
    button.setText(label)
    button.setAccessibleName(label)
    button.setToolTip(help_text)
    button.setIcon(QgsApplication.getThemeIcon("/" + icon))
    button.setIconSize(QSize(20, 20))
    button.setFixedSize(28, 28)
    return button


class SelectionTools(QWidget):
    currentTextChanged = pyqtSignal(str)
    brushRadiusChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = "Pointer"
        self.buttons = {}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        specs = (
            ("Pointer", "Navigate", "mActionPan.svg",
             "Navigate: orbit, pan and zoom without selecting or editing. In a Slice, pan and zoom keep the profile orientation."),
            ("Polygon", "Polygon Select", "mActionSelectPolygon.svg",
             "Polygon Select: click vertices, then double-click, Enter or right-click to finish; Escape cancels. Selects original points within the active depth limits, not just displayed points. 3D views temporarily use top view; Slice stays in profile."),
            ("Rectangle", "Rectangle Select", "mActionSelectRectangle.svg",
             "Rectangle Select: drag a rectangle; Escape cancels. Selects original points within the active depth limits. 3D views temporarily use top view; Slice stays in profile. Staged edits are unchanged until you apply an edit."),
            ("Circle", "Circle Select", "mActionSelectRadius.svg",
             "Circle Select: drag from the center to set a radius in dataset XY coordinates; Escape cancels. Full column selects a circular column; Elevation or HAG limits make it a bounded cylinder. Selection resolves original points, not displayed samples. Vertical Slice support is not yet enabled."),
            ("Brush", "Brush Select", "mActionSelectFreehand.svg",
             "Brush Select: drag a continuous round stroke with radius in dataset XY units. Full column selects through the cloud; Elevation or HAG limits bound its depth. Shift adds and Alt subtracts. Original points are resolved in the background; screen pixels are never edit addresses. Vertical Slice support is not yet enabled."),
        )
        for value, label, icon, help_text in specs:
            button = spatial_button(label, icon, help_text, self)
            button.setCheckable(True)
            button.setChecked(value == self._value)
            button.clicked.connect(lambda _=False, v=value: self.activate(v))
            self.group.addButton(button)
            self.buttons[value] = button
            layout.addWidget(button)
        self.brush_label = QLabel("Radius")
        self.brush_radius = QDoubleSpinBox()
        self.brush_radius.setRange(.001, 1000000)
        self.brush_radius.setDecimals(3)
        self.brush_radius.setValue(1)
        self.brush_radius.setKeyboardTracking(False)
        self.brush_radius.setAccessibleName("Brush radius in dataset XY units")
        self.brush_radius.setToolTip("Round Brush radius in dataset XY coordinate units. Elevation or HAG limits independently control vertical depth.")
        self.brush_radius.setMaximumWidth(105)
        self.brush_radius.valueChanged.connect(self.brushRadiusChanged.emit)
        layout.addWidget(self.brush_label)
        layout.addWidget(self.brush_radius)
        self._show_brush_options(False)

    def currentText(self):
        return self._value

    def setCurrentText(self, value):
        if value not in self.buttons or value == self._value:
            return
        self._value = value
        self.buttons[value].setChecked(True)
        self._show_brush_options(value == "Brush")
        self.currentTextChanged.emit(value)

    def activate(self, value):
        if value == self._value:
            self.currentTextChanged.emit(value)
        else:
            self.setCurrentText(value)

    def brushRadius(self):
        return self.brush_radius.value()

    def setBrushRadius(self, value):
        self.brush_radius.blockSignals(True)
        self.brush_radius.setValue(value)
        self.brush_radius.blockSignals(False)

    def _show_brush_options(self, visible):
        self.brush_label.setVisible(visible)
        self.brush_radius.setVisible(visible)
