"""Compact, shared display-only point shape and screen-size controls."""
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QSpinBox
from ..core.point_cloud.point_appearance import POINT_STYLES
from ..compat.qt import qt_enum


class PointAppearance(QWidget):
    def __init__(self, send, parent=None):
        super().__init__(parent)
        self.send = send
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.style_combo = QComboBox()
        self.style_combo.addItems(POINT_STYLES)
        self.style_combo.setSizeAdjustPolicy(qt_enum(QComboBox, "AdjustToContents", "SizeAdjustPolicy"))
        self.style_combo.setAccessibleName("Point style")
        self.style_combo.setToolTip("Point style: Circular draws round screen sprites; Square draws square sprites. Changes display only, never selection, source attributes or export.")
        row.addWidget(self.style_combo)
        row.addWidget(QLabel("Size"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(0, 16)
        self.size_spin.setSpecialValueText("Automatic")
        self.size_spin.setSuffix(" px")
        self.size_spin.setFixedWidth(105)
        self.size_spin.setAccessibleName("Point size")
        self.size_spin.setToolTip("Automatic preserves adaptive 2-5 pixel sizing. Choose 1-16 pixels for a fixed screen size. This does not change point density, voxel size, selection depth or exported points.")
        row.addWidget(self.size_spin)
        self.style_combo.currentTextChanged.connect(self.changed)
        self.size_spin.valueChanged.connect(self.changed)

    def changed(self, *_):
        self.send({"action": "point_display", "style": self.style_combo.currentText(), "size": self.size_spin.value()})

    def sync(self, state):
        for control in (self.style_combo, self.size_spin):
            control.blockSignals(True)
        self.style_combo.setCurrentText(state.get("point_style", "Circular"))
        if not self.size_spin.hasFocus():
            self.size_spin.setValue(state.get("point_size", 0))
        for control in (self.style_combo, self.size_spin):
            control.blockSignals(False)
