"""Compact presentation-only display range control for point-cloud views."""
from qgis.PyQt.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QWidget


class DisplayRangeControls(QWidget):
    def __init__(self, send, parent=None):
        super().__init__(parent)
        self.send = send
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        row.addWidget(QLabel("Range"))
        self.mode = QComboBox()
        self.mode.addItems(("Auto", "Robust", "Manual"))
        self.mode.setAccessibleName("Display range mode")
        self.mode.setToolTip("Display-only color range. It does not hide points, change selection, or modify the source.")
        row.addWidget(self.mode)
        self.minimum = QDoubleSpinBox()
        self.maximum = QDoubleSpinBox()
        for control in (self.minimum, self.maximum):
            control.setRange(-1e12, 1e12)
            control.setDecimals(3)
            control.setFixedWidth(78)
        self.minimum.setPrefix("min ")
        self.maximum.setPrefix("max ")
        row.addWidget(self.minimum)
        row.addWidget(self.maximum)
        self.apply_button = QPushButton("Apply")
        self.apply_button.setToolTip("Apply the manual display range to the current attribute.")
        row.addWidget(self.apply_button)
        self.mode.currentTextChanged.connect(self._mode_changed)
        self.apply_button.clicked.connect(self.apply)
        self._set_manual_visible(False)

    def _set_manual_visible(self, visible):
        self.minimum.setVisible(visible)
        self.maximum.setVisible(visible)
        self.apply_button.setVisible(visible)

    def _mode_changed(self, value):
        manual = value == "Manual"
        self._set_manual_visible(manual)
        if value == "Auto":
            self.send({"action": "display_range_mode", "mode": "AUTO"})
        elif value == "Robust":
            self.send({"action": "display_range_mode", "mode": "ROBUST"})

    def apply(self):
        low, high = self.minimum.value(), self.maximum.value()
        if low < high:
            self.send({"action": "display_range", "minimum": low, "maximum": high, "mode": "MANUAL"})

    def sync(self, telemetry):
        display_range = telemetry.get("display_range") or telemetry.get("z_range")
        if display_range and len(display_range) == 2:
            for control, value in ((self.minimum, display_range[0]), (self.maximum, display_range[1])):
                control.blockSignals(True)
                control.setValue(float(value))
                control.blockSignals(False)
        mode = str(telemetry.get("display_range_mode", "AUTO")).title()
        if mode not in ("Auto", "Robust", "Manual"):
            mode = "Auto"
        self.mode.blockSignals(True)
        self.mode.setCurrentText(mode)
        self.mode.blockSignals(False)
        self._set_manual_visible(mode == "Manual")
