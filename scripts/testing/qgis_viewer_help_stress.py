"""Qt5/Qt6 widget-only geometry gate: 1,000 help changes, no science or renderer."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QT_VERSION_STR
from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage

app = QgsApplication([], True)
app.initQgis()
page = PointCloudPage()
canvas = page.surface
help_box = page.context_help
page.resize(760, 650)
page.show()
app.processEvents()
baseline = (canvas.width(), canvas.height(), help_box.height())
for index in range(1000):
    help_box.set_help(("Polygon selection. " * (index % 90)) or "RGB")
    page.status.setText(("RGB diagnosis. " * (index % 70)) or "Ready")
    page.editor.summary.setText(("Selected original points. " * (index % 40)) or "No selection")
    app.processEvents()
    assert (canvas.width(), canvas.height(), help_box.height()) == baseline, index
print(json.dumps({"passed": True, "messages": 1000, "qt": QT_VERSION_STR, "geometry": baseline}), flush=True)
page.close()
app.exitQgis()
