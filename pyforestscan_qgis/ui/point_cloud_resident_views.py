"""Bounded warm renderers; source selection and edits remain in EditorPanel."""
from collections import OrderedDict
from copy import deepcopy


class ResidentViews:
    """Keep Overview/Detail/Slice warm without running inactive render loops."""

    fields = ("_view_state", "_source_info", "_render_only",
              "_filter_bounds_initialized", "_restore_after_open", "_restore_expected")

    def __init__(self, page, capacity=3):
        self.page = page
        self.capacity = capacity
        self.parked = OrderedDict()
        self.key = None
        self.geometry = None

    def started(self):
        view = self.page.linked.active()
        self.key = view.view_id
        self.geometry = deepcopy(view.geometry)
        while len(self.parked) >= self.capacity:
            self.discard(next(iter(self.parked)))

    def _replace_surface(self, surface):
        page = self.page
        old = page.surface
        item = page.layout().replaceWidget(old, surface)
        del item
        old.hide()
        page.surface = surface
        surface.show()
        return old

    def prepare(self, view):
        page = self.page
        if page.worker and self.key != view.view_id:
            self.park()
        entry = self.parked.get(view.view_id)
        if entry and entry["geometry"] != view.geometry:
            self.discard(view.view_id)
            entry = None
        if not entry:
            return False
        self.parked.pop(view.view_id)
        worker = entry["worker"]
        worker.update.disconnect(entry["update"])
        worker.finished.disconnect(entry["finished"])
        placeholder = self._replace_surface(entry["surface"])
        placeholder.deleteLater()
        page.worker = worker
        self.key, self.geometry = view.view_id, entry["geometry"]
        for name, value in entry["state"].items():
            setattr(page, name, value)
        page._pending_source = None
        page.linked.waiting = False
        page.linked.context_sent = True
        page.linked.rendered_id = view.view_id
        worker.update.connect(page._update)
        worker.finished.connect(page._finished)
        worker.send({"action": "visible", "visible": True})
        worker.send({"action": "resize", "width": page.surface.width(), "height": page.surface.height()})
        page._restore_after_open = None
        page._restore_expected = None
        state = page._view_state or {}
        page.editor.viewer_worker = worker
        page.editor.sent_overlay = None
        event = state.get("editor", {}).get("event") or {}
        page.editor.event_id = event.get("id")
        page.linked.event_id = event.get("id")
        for combo, value in ((page.mode, state.get("mode", "Classification")),
                             (page.quality, state.get("quality", "Automatic"))):
            combo.blockSignals(True)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        limits = state.get("height_filter")
        page.height_enabled.blockSignals(True)
        page.height_enabled.setChecked(limits is not None)
        page.height_enabled.blockSignals(False)
        for control, value in zip((page.height_min, page.height_max),
                                  limits or state.get("z_range", (0, 50))):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
        page._sync_classes(state.get("classes"))
        page.linked.apply_navigation(view)
        page._update({"telemetry": state})
        page.open_button.setEnabled(True)
        page.reload_button.setEnabled(True)
        return True

    def park(self):
        page = self.page
        worker = page.worker
        if worker is None:
            return
        from .point_cloud_page import ViewerSurface
        key = self.key
        # Only acknowledged, fully opened views are reusable.
        if (not key or key not in page.workspace.views or
                page.linked.rendered_id != key or not page._view_state):
            return
        entry = {"worker": worker, "surface": page.surface,
                 "geometry": deepcopy(self.geometry),
                 "state": {name: getattr(page, name) for name in self.fields}}
        def update(value):
            if value.get("telemetry", {}).get("ready"):
                entry["state"]["_view_state"] = value["telemetry"]
        def finished():
            if self.parked.get(key) is entry:
                self.parked.pop(key)
                entry["surface"].deleteLater()
        entry.update(update=update, finished=finished)
        worker.update.disconnect(page._update)
        worker.finished.disconnect(page._finished)
        worker.update.connect(update)
        worker.finished.connect(finished)
        self.parked[key] = entry
        worker.send({"action": "visible", "visible": False})
        self._replace_surface(ViewerSurface(page))
        page.worker = None
        page._view_state = None
        self.key = None
        while len(self.parked) > self.capacity:
            self.discard(next(iter(self.parked)))

    def discard(self, key):
        entry = self.parked.pop(key, None)
        if entry:
            worker = entry["worker"]
            worker.update.disconnect(entry["update"])
            worker.finished.disconnect(entry["finished"])
            worker.finished.connect(entry["surface"].deleteLater)
            worker.stop("inactive_view_evicted")

    def clear(self):
        for key in list(self.parked):
            self.discard(key)
        self.key = None
        self.geometry = None
