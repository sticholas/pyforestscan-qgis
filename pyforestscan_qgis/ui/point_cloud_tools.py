"""Compact QGIS-theme tools; no additional selection or editing state."""
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QToolButton, QButtonGroup


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
        )
        for value, label, icon, help_text in specs:
            button = spatial_button(label, icon, help_text, self)
            button.setCheckable(True)
            button.setChecked(value == self._value)
            button.clicked.connect(lambda _=False, v=value: self.activate(v))
            self.group.addButton(button)
            self.buttons[value] = button
            layout.addWidget(button)

    def currentText(self):
        return self._value

    def setCurrentText(self, value):
        if value not in self.buttons or value == self._value:
            return
        self._value = value
        self.buttons[value].setChecked(True)
        self.currentTextChanged.emit(value)

    def activate(self, value):
        if value == self._value:
            self.currentTextChanged.emit(value)
        else:
            self.setCurrentText(value)
