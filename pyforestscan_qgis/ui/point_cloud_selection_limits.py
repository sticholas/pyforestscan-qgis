"""Shared next-selection limits; the linked controller owns the actual values."""
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QDoubleSpinBox
from ..compat.qt import qt_enum


class SelectionLimits(QWidget):
    def __init__(self, controller, view_id=None, parent=None):
        super().__init__(parent)
        self.controller, self.view_id = controller, view_id
        self.syncing = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        label = QLabel("Selection limits")
        label.setToolTip("Limits apply to the next selection. Changing them does not alter the current selection or staged edits.")
        row.addWidget(label)
        self.mode = QComboBox()
        self.mode.setSizeAdjustPolicy(qt_enum(QComboBox, "AdjustToContents", "SizeAdjustPolicy"))
        self.mode.setAccessibleName("Selection limit mode")
        self.mode.setToolTip("Full column uses all heights within the drawn shape. Elevation uses original Z; HAG uses stored HeightAboveGround. Slice thickness always limits profile selections.")
        row.addWidget(self.mode)
        self.minimum, self.maximum = QDoubleSpinBox(), QDoubleSpinBox()
        for control, name in ((self.minimum, "Minimum"), (self.maximum, "Maximum")):
            control.setRange(-10000000, 10000000)
            control.setDecimals(3)
            control.setKeyboardTracking(False)
            control.setFixedWidth(125)
            control.setPrefix("Min " if name == "Minimum" else "Max ")
            control.setAccessibleName(name + " selection height")
            control.setToolTip(name + " inclusive height in the source's stored Z or HeightAboveGround units, not camera depth. These limits do not calculate HAG.")
            row.addWidget(control)
            control.valueChanged.connect(self.changed)
        self.context = QLabel()
        self.context.setToolTip("Slice width uses dataset XY units. Height limits use stored height units; no unit conversion is implied.")
        row.addWidget(self.context)
        row.addStretch(1)
        self.mode.currentIndexChanged.connect(self.changed)
        controller.limitsChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.syncing = True
        controller = self.controller
        view = controller.page.workspace.views.get(self.view_id or controller.page.workspace.active_view_id)
        is_slice = view is not None and view.view_type == "VERTICAL_SLICE"
        choices = [("Within slice thickness" if is_slice else "Full column", ""),
                   ("Elevation range (Z)", "z_filter")]
        if "HeightAboveGround" in controller.page.editor.state.get("dimensions", []):
            choices.append(("Height above ground (HAG)", "hag_filter"))
        elif "hag_filter" in controller.depth:
            choices.append(("HAG unavailable", "hag_filter"))
        if [(self.mode.itemText(i), self.mode.itemData(i)) for i in range(self.mode.count())] != choices:
            self.mode.clear()
            for label, value in choices:
                self.mode.addItem(label, value)
        key = next(iter(controller.depth), "")
        index = self.mode.findData(key)
        self.mode.setCurrentIndex(max(0, index))
        limits = controller.depth.get(key, (0, 50))
        # Telemetry refresh must not overwrite a partially typed numeric value.
        for control, value in zip((self.minimum, self.maximum), limits):
            if not control.hasFocus():
                control.setValue(value)
        for control in (self.minimum, self.maximum):
            control.setVisible(bool(key))
        parts = []
        if is_slice:
            parts.append(f"Slice: {view.geometry['thickness']:g} XY units")
            interval = view.geometry.get("vertical_limits")
            if interval:
                axis = "HAG" if view.geometry.get("vertical_axis") == "HeightAboveGround" else "Z"
                parts.append(f"{axis}: {interval[0]:g}-{interval[1]:g}")
        if key:
            parts.append("stored height units")
        if controller.depth_error:
            parts = [controller.depth_error]
        self.context.setText(" | ".join(parts))
        self.setEnabled(bool(controller.page.editor.state.get("ready")) and not controller.page.editor.busy)
        self.syncing = False

    def changed(self):
        if self.syncing:
            return
        key = self.mode.currentData()
        self.controller.set_depth({key: [self.minimum.value(), self.maximum.value()]} if key else {})
