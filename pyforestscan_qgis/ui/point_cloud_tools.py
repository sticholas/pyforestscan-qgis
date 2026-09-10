"""Compact QGIS-theme tools; no additional selection or editing state."""
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize, pyqtSignal
from qgis.PyQt.QtWidgets import (QWidget, QHBoxLayout, QToolButton, QButtonGroup,
                                 QLabel, QDoubleSpinBox, QComboBox)


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
    spherePlacementChanged = pyqtSignal(str, float)

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
            ("Box", "Box Select", "mActionSelectRectangle.svg",
             "Box Select: in Overview or Area Detail, first choose explicit Elevation or HAG limits, then drag the XY footprint. In Vertical Slice, drag a profile rectangle; slice thickness supplies depth. The full-resolution source query uses those exact bounds."),
            ("Circle", "Circle Select", "mActionSelectRadius.svg",
             "Circle Select: drag from the center to set a radius in dataset XY coordinates; Escape cancels. Full column selects a circular column; Elevation or HAG limits make it a bounded cylinder. Selection resolves original points, not displayed samples. Vertical Slice support is not yet enabled."),
            ("Sphere", "Sphere Select", "mIconPointCloudLayer.svg",
             "Sphere Select: choose an explicit source Z or stored HAG center, then drag center-to-edge for radius in source coordinate units. Exact 3D membership resolves against original points. Camera depth and displayed samples are never selection authority. Vertical Slice support is not enabled."),
            ("Brush", "Brush Select", "mActionSelectFreehand.svg",
             "Brush Select: drag a continuous round stroke. In 3D views, radius uses dataset XY units and optional height limits control depth. In Profile, radius uses distance/elevation or HAG units inside the source corridor. Shift adds and Alt subtracts. Original points are resolved in the background; screen pixels are never edit addresses."),
            ("AboveLine", "Select Above Line", "mActionArrowUp.svg",
             "Select Above Line: in Vertical Slice, draw two points across the profile. Selects original points above the exact source-coordinate line, within its horizontal span and the slice corridor."),
            ("BelowLine", "Select Below Line", "mActionArrowDown.svg",
             "Select Below Line: in Vertical Slice, draw two points across the profile. Selects original points below the exact source-coordinate line, within its horizontal span and the slice corridor."),
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
        self.brush_radius.setAccessibleName(
            "Brush radius in dataset XY or active Profile coordinate units")
        self.brush_radius.setToolTip("Round Brush radius in dataset XY units for 3D views, or distance/elevation or HAG units in Profile. Source points are resolved independently of display density.")
        self.brush_radius.setMaximumWidth(105)
        self.brush_radius.valueChanged.connect(self.brushRadiusChanged.emit)
        layout.addWidget(self.brush_label)
        layout.addWidget(self.brush_radius)
        self.sphere_label = QLabel("Center")
        self.sphere_axis = QComboBox()
        self.sphere_axis.addItem("Z", "Z")
        self.sphere_axis.setAccessibleName("Sphere center height axis")
        self.sphere_axis.setToolTip("Use source elevation Z or stored HeightAboveGround for the exact sphere center.")
        self.sphere_height = QDoubleSpinBox()
        self.sphere_height.setRange(-10000000, 10000000)
        self.sphere_height.setDecimals(3)
        self.sphere_height.setKeyboardTracking(False)
        self.sphere_height.setAccessibleName("Sphere center height")
        self.sphere_height.setToolTip("Exact sphere-center height in the selected stored source dimension. This is not camera depth.")
        self.sphere_height.setMaximumWidth(115)
        self.sphere_axis.currentIndexChanged.connect(self._sphere_changed)
        self.sphere_height.valueChanged.connect(self._sphere_changed)
        layout.addWidget(self.sphere_label)
        layout.addWidget(self.sphere_axis)
        layout.addWidget(self.sphere_height)
        self._show_options()
        self.setProfileToolsVisible(False)

    def currentText(self):
        return self._value

    def setCurrentText(self, value):
        if value not in self.buttons or value == self._value:
            return
        self._value = value
        self.buttons[value].setChecked(True)
        self._show_options()
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

    def sphereAxis(self):
        return self.sphere_axis.currentData()

    def sphereHeight(self):
        return self.sphere_height.value()

    def setSpherePlacement(self, axis, height, has_hag=True):
        self.sphere_axis.blockSignals(True)
        self.sphere_height.blockSignals(True)
        existing = [self.sphere_axis.itemData(i) for i in range(self.sphere_axis.count())]
        if has_hag and "HeightAboveGround" not in existing:
            self.sphere_axis.addItem("HAG", "HeightAboveGround")
        elif not has_hag and "HeightAboveGround" in existing:
            self.sphere_axis.removeItem(existing.index("HeightAboveGround"))
        index = self.sphere_axis.findData(axis)
        self.sphere_axis.setCurrentIndex(max(0, index))
        if not self.sphere_height.hasFocus():
            self.sphere_height.setValue(height)
        self.sphere_axis.blockSignals(False)
        self.sphere_height.blockSignals(False)

    def setProfileToolsVisible(self, visible):
        for name in ("AboveLine", "BelowLine"):
            self.buttons[name].setVisible(bool(visible))

    def _sphere_changed(self, _value=None):
        self.spherePlacementChanged.emit(self.sphereAxis(), self.sphereHeight())
        if self._value == "Sphere":
            self.currentTextChanged.emit("Sphere")

    def _show_options(self):
        brush = self._value == "Brush"
        sphere = self._value == "Sphere"
        self.brush_label.setVisible(brush)
        self.brush_radius.setVisible(brush)
        for widget in (self.sphere_label, self.sphere_axis, self.sphere_height):
            widget.setVisible(sphere)
