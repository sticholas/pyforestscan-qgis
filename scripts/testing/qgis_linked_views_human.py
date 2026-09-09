"""Bounded human linked-view test window with owned-worker shutdown."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--duration",type=int,default=900)
    args=parser.parse_args()
    if not 60<=args.duration<=7200:
        parser.error("Human session must be bounded to 60-7200 seconds.")
    args.output_dir.mkdir(parents=True,exist_ok=False)
    from qgis.core import QgsApplication,Qgis
    from qgis.PyQt.QtCore import QTimer,QObject,QEvent
    from pyforestscan_qgis.compat.qt import qt_enum
    from pyforestscan_qgis.ui.point_cloud_page import PointCloudPage
    app=QgsApplication([],True)
    app.initQgis()
    app.setQuitOnLastWindowClosed(False)
    page=PointCloudPage()
    page.setWindowTitle("PyForestScan linked views: human acceptance")
    page.resize(1100,900)
    page.show()
    page.raise_()
    page.activateWindow()
    started=time.monotonic()
    finishing=False
    report={"qgis":Qgis.QGIS_VERSION,"source":str(args.source),"human_acceptance":"PENDING_USER_REPORT","samples":[]}
    page.source.setText(str(args.source))
    page.start_source(str(args.source))
    def finish():
        nonlocal finishing
        if finishing:
            return
        finishing=True
        timer.stop()
        report["workspace"]=page.workspace.to_dict()
        report["editor"]=page.editor.state
        workers=[w for w in (page.worker,page.editor.worker,page.linked.query_worker,
                 *(window.worker for window in page.linked.detached.values())) if w]
        events=[w.stopped_event for w in workers]
        page.prepare_for_unload()
        def drain():
            if not all(event.is_set() for event in events):
                QTimer.singleShot(100,drain)
                return
            report["elapsed_seconds"]=time.monotonic()-started
            (args.output_dir/"human.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
            print(json.dumps({"closed":True,"evidence":str(args.output_dir)}),flush=True)
            page.close()
            app.quit()
        drain()
    class CloseGuard(QObject):
        def eventFilter(self,watched,event):
            if event.type()==qt_enum(QEvent,"Close","Type") and not finishing:
                finish()
                return True
            return False
    guard=CloseGuard(page)
    page.installEventFilter(guard)
    def sample():
        if time.monotonic()-started>=args.duration or (args.output_dir/"close-request").exists():
            finish()
            return
        report["samples"].append({"elapsed":time.monotonic()-started,"status":page.status.text(),
            "selection":page.editor.state.get("selection"),"edits":page.editor.state.get("edits"),
            "active":page.workspace.active_view_id,"detached":list(page.linked.detached),
            "viewer":page._view_state})
        (args.output_dir/"progress.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    timer=QTimer()
    timer.timeout.connect(sample)
    timer.start(2000)
    print(json.dumps({"opened":True,"duration":args.duration,"evidence":str(args.output_dir)}),flush=True)
    return app.exec() if hasattr(app,"exec") else app.exec_()


if __name__=="__main__":
    raise SystemExit(main())
