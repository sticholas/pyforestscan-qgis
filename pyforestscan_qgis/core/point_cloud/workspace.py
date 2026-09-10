"""QGIS-free linked-view registry around ONE authoritative managed editor.

This is a control-plane foundation, not a second journal, point store, or a
replacement selection resolver. Detail/profile renderers remain gated.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, asdict
from enum import Enum
import math
import re
from uuid import uuid4


class ViewType(str, Enum):
    OVERVIEW_3D = "OVERVIEW_3D"
    AREA_DETAIL = "AREA_DETAIL"
    VERTICAL_SLICE = "VERTICAL_SLICE"


MAX_VIEW_BOOKMARKS = 100
MAX_VIEW_TITLE = 80
SCENE_OVERLAY_KEYS = ("selection", "measurements", "annotations", "profiles")


def scene_visibility(values=None):
    """Validated per-view overlay visibility; never selection/edit authority."""
    result = {key: True for key in SCENE_OVERLAY_KEYS}
    if values is None:
        return result
    if not isinstance(values, dict) or set(values) - set(SCENE_OVERLAY_KEYS):
        raise ValueError("Scene visibility contains an unsupported overlay.")
    if any(type(value) is not bool for value in values.values()):
        raise ValueError("Scene overlay visibility values must be true or false.")
    result.update(values)
    return result


def _view_title(value):
    title = value.strip() if isinstance(value, str) else ""
    if (not title or len(title) > MAX_VIEW_TITLE
            or any(ord(char) < 32 for char in title)):
        raise ValueError(f"Linked view name must contain 1 to {MAX_VIEW_TITLE} printable characters.")
    return title


def _camera(value):
    if not isinstance(value, dict):
        raise ValueError("A saved viewpoint requires camera values.")
    position = tuple(value.get("position", ()))
    result = {"position": position, "yaw": value.get("yaw"),
              "pitch": value.get("pitch"), "radius": value.get("radius")}
    scalars = (*position, result["yaw"], result["pitch"], result["radius"])
    if (len(position) != 3 or any(type(item) not in (int, float)
                                  or not math.isfinite(item) for item in scalars)
            or result["radius"] <= 0):
        raise ValueError("A saved viewpoint requires a finite camera and positive radius.")
    return result


@dataclass(frozen=True)
class ViewBookmark:
    bookmark_id: str
    name: str
    view_id: str
    view_type: ViewType
    camera: dict

    def __post_init__(self):
        name = self.name.strip() if isinstance(self.name, str) else ""
        if (not re.fullmatch(r"[0-9a-f]{32}", self.bookmark_id)
                or not name or len(name) > 80 or any(ord(char) < 32 for char in name)
                or not self.view_id):
            raise ValueError("Saved viewpoint identity or name is invalid.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "view_type", ViewType(self.view_type))
        object.__setattr__(self, "camera", _camera(deepcopy(self.camera)))


@dataclass(frozen=True)
class AreaGeometry:
    shape: str
    crs: str
    center: tuple = ()
    width: float | None = None
    height: float | None = None
    radius: float | None = None
    vertices: tuple = ()
    unit_label: str = "source coordinate units"

    def __post_init__(self):
        if self.shape not in ("RECTANGLE", "SQUARE", "CIRCLE", "POLYGON") or not self.crs.strip():
            raise ValueError("Area requires a supported shape and source CRS.")
        object.__setattr__(self, "center", tuple(self.center))
        object.__setattr__(self, "vertices", tuple(tuple(p) for p in self.vertices))
        if self.shape == "POLYGON":
            if not 4 <= len(self.vertices) <= 4097 or self.vertices[0] != self.vertices[-1]:
                raise ValueError("Area polygon must be closed.")
            coordinates = self.vertices
        else:
            coordinates = (self.center,)
            sizes = (self.radius,) if self.shape == "CIRCLE" else (self.width, self.height)
            if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in sizes):
                raise ValueError("Area dimensions must be positive source-unit values.")
            if self.shape == "SQUARE" and self.width != self.height:
                raise ValueError("Square width and height must agree.")
        if any(len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point) for point in coordinates):
            raise ValueError("Area requires finite source XY coordinates.")


@dataclass(frozen=True)
class SliceGeometry:
    a: tuple
    b: tuple
    thickness: float
    crs: str
    vertical_axis: str = "Z"
    vertical_limits: tuple | None = None
    path: tuple = ()
    display_projection: str = "SOURCE_XY"

    def __post_init__(self):
        object.__setattr__(self, "a", tuple(self.a))
        object.__setattr__(self, "b", tuple(self.b))
        path = tuple(tuple(point) for point in self.path) if self.path else (self.a, self.b)
        object.__setattr__(self, "path", path if len(path) > 2 else ())
        values = (*self.a, *self.b, self.thickness, *(value for point in path for value in point))
        if len(self.a) != 2 or len(self.b) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError("Slice requires finite source XY endpoints and thickness.")
        if self.a == self.b or self.thickness <= 0 or not self.crs.strip():
            raise ValueError("Slice needs distinct endpoints, positive thickness and CRS.")
        if (not 2 <= len(path) <= 256 or any(len(point) != 2 for point in path)
                or any(first == second for first, second in zip(path, path[1:]))
                or path[0] != self.a or path[-1] != self.b):
            raise ValueError("Profile path requires 2-256 distinct consecutive source XY points matching its endpoints.")
        if self.vertical_axis not in ("Z", "HeightAboveGround"):
            raise ValueError("Slice vertical axis must be Z or HeightAboveGround.")
        if self.display_projection not in ("SOURCE_XY", "PROFILE_DISTANCE"):
            raise ValueError("Profile display projection is unsupported.")
        if self.vertical_limits is not None:
            limits = tuple(self.vertical_limits)
            if len(limits) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in limits) or limits[0] >= limits[1]:
                raise ValueError("Invalid slice vertical limits.")
            object.__setattr__(self, "vertical_limits", limits)

    @property
    def length(self):
        return sum(math.hypot(second[0]-first[0], second[1]-first[1])
                   for first, second in zip(self.points, self.points[1:]))

    @property
    def points(self):
        return self.path or (self.a, self.b)

    def local(self, x, y, z, *, hag=None):
        """Along-distance, vertical coordinate, signed cross-track distance."""
        height = hag if self.vertical_axis == "HeightAboveGround" else z
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y, height)):
            raise ValueError("Finite source coordinates and the selected height dimension are required.")
        best = None
        cumulative = 0.0
        for first, second in zip(self.points, self.points[1:]):
            dx, dy = second[0]-first[0], second[1]-first[1]
            length = math.hypot(dx, dy)
            fraction = max(0.0, min(1.0,
                ((x-first[0])*dx+(y-first[1])*dy)/(length*length)))
            px, py = first[0]+fraction*dx, first[1]+fraction*dy
            distance2 = (x-px)**2+(y-py)**2
            candidate = (distance2, cumulative+fraction*length,
                         (-(x-first[0])*dy+(y-first[1])*dx)/length)
            if best is None or candidate[0] < best[0]:
                best = candidate
            cumulative += length
        return best[1], height, best[2]

    def corridor(self):
        if self.path:
            margin = self.thickness/2
            xs = [point[0] for point in self.points]
            ys = [point[1] for point in self.points]
            xmin, xmax, ymin, ymax = min(xs)-margin, max(xs)+margin, min(ys)-margin, max(ys)+margin
            return ((xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax),(xmin,ymin))
        nx = -(self.b[1]-self.a[1])/self.length*self.thickness/2
        ny = (self.b[0]-self.a[0])/self.length*self.thickness/2
        a, b = self.a, self.b
        return ((a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),
                (b[0]-nx,b[1]-ny),(a[0]-nx,a[1]-ny),(a[0]+nx,a[1]+ny))

    def segment_corridors(self):
        """Display-only segment rectangles; exact membership uses path distance."""
        result = []
        for first, second in zip(self.points, self.points[1:]):
            length = math.hypot(second[0]-first[0], second[1]-first[1])
            nx = -(second[1]-first[1])/length*self.thickness/2
            ny = (second[0]-first[0])/length*self.thickness/2
            result.append(((first[0]+nx,first[1]+ny),(second[0]+nx,second[1]+ny),
                           (second[0]-nx,second[1]-ny),(first[0]-nx,first[1]-ny),
                           (first[0]+nx,first[1]+ny)))
        return tuple(result)


@dataclass
class ViewState:
    view_id: str
    view_type: ViewType
    title: str
    geometry: dict = field(default_factory=dict)
    camera: dict = field(default_factory=dict)
    display_filters: dict = field(default_factory=dict)
    render_mode: str = "Classification"
    lod: dict = field(default_factory=dict)
    scene_visibility: dict = field(default_factory=scene_visibility)


class ViewerResourceCoordinator:
    """Only active views receive a render allocation; inactive metadata is cheap."""
    def visible_allocations(self, roots, focused_id, *, point_budget):
        if type(point_budget) is not int or point_budget < 0 or focused_id not in roots:
            raise ValueError("Invalid visible-view allocation.")
        if any(type(value) is not int or value < 0 for value in roots.values()):
            raise ValueError("Invalid visible root sizes.")
        ordered = [focused_id, *(key for key in roots if key != focused_id)]
        result, remaining = {}, point_budget
        for key in ordered:
            minimum = max(1000, roots[key])
            result[key] = minimum if remaining >= minimum else 0
            remaining -= result[key]
        weights = {key:2 if key == focused_id else 1 for key in result if result[key]}
        total = sum(weights.values())
        for key,weight in weights.items():
            result[key] += remaining*weight//total
        return result

    def allocations(self, view_ids, active_id, *, point_budget, available_ram, frame_ms):
        if active_id not in view_ids:
            raise ValueError("Active view is not registered.")
        if type(point_budget) is not int or point_budget < 0 or available_ram < 0 or not math.isfinite(frame_ms) or frame_ms < 0:
            raise ValueError("Invalid resource measurements.")
        # Conservative accounting allowance, not a measured GPU byte count.
        budget = min(point_budget, int(available_ram // 128))
        if frame_ms > 50:
            budget = int(budget * .75)
        return {key: {"points": budget if key == active_id else 0,
                      "suspended": key != active_id} for key in view_ids}


class PointCloudWorkspaceModel:
    SCHEMA = 2

    def __init__(self, command_sink=None):
        self._sink = command_sink
        self._views = {}
        self._subscribers = {}
        self.observer_errors = {}
        self.source_fingerprint = ""
        self.session_id = ""
        self.active_view_id = ""
        self.global_filters = {}
        self._bookmarks = {}
        self._editor = {}
        self.resources = ViewerResourceCoordinator()

    def bind_editor(self, sink):
        self._sink = sink

    def detach_editor(self):
        self._editor = {}
        self.source_fingerprint = self.session_id = ""
        self.global_filters = {}
        self._bookmarks = {}
        for key in list(self._views):
            if self._views[key].view_type != ViewType.OVERVIEW_3D:
                self.close_view(key)
        for key, callback in tuple(self._subscribers.items()):
            try:
                callback({})
            except Exception as error:
                self.observer_errors[key] = str(error)[:500]

    @property
    def views(self):
        return deepcopy(self._views)

    @property
    def bookmarks(self):
        return deepcopy(self._bookmarks)

    def add_bookmark(self, name, view_id, camera, *, bookmark_id=None):
        if view_id not in self._views:
            raise ValueError("A saved viewpoint must belong to an existing linked view.")
        if len(self._bookmarks) >= MAX_VIEW_BOOKMARKS:
            raise ValueError(f"One workspace supports at most {MAX_VIEW_BOOKMARKS} saved viewpoints.")
        key = bookmark_id or uuid4().hex
        if key in self._bookmarks:
            raise ValueError("Saved viewpoint identity must be unique.")
        item = ViewBookmark(key, name, view_id, self._views[view_id].view_type, camera)
        self._bookmarks[key] = item
        return key

    def remove_bookmark(self, bookmark_id):
        if bookmark_id not in self._bookmarks:
            raise ValueError("Unknown saved viewpoint.")
        del self._bookmarks[bookmark_id]

    def activate_bookmark(self, bookmark_id):
        if bookmark_id not in self._bookmarks:
            raise ValueError("Unknown saved viewpoint.")
        item = self._bookmarks[bookmark_id]
        view = self._views.get(item.view_id)
        if view is None or view.view_type != item.view_type:
            raise ValueError("The linked view for this saved viewpoint is no longer available.")
        self.update_view(item.view_id, camera=item.camera)
        self.activate(item.view_id)
        return deepcopy(item)

    @property
    def editor_snapshot(self):
        return deepcopy(self._editor)

    def register(self, view_type=ViewType.OVERVIEW_3D, title="3D Overview", *, view_id=None, geometry=None):
        kind = ViewType(view_type)
        key = view_id or uuid4().hex
        title = _view_title(title)
        if not isinstance(key, str) or not key or key in self._views:
            raise ValueError("View identity must be unique.")
        if any(item.title.casefold() == title.casefold() for item in self._views.values()):
            raise ValueError("Linked view names must be unique in this workspace.")
        if kind != ViewType.OVERVIEW_3D and not geometry:
            raise ValueError("A detail or slice view requires source-space geometry.")
        if kind == ViewType.VERTICAL_SLICE:
            SliceGeometry(**geometry)
        if kind == ViewType.AREA_DETAIL:
            AreaGeometry(**geometry)
        self._views[key] = ViewState(key, kind, title, deepcopy(geometry or {}))
        if not self.active_view_id:
            self.active_view_id = key
        return key

    def rename_view(self, view_id, title):
        if view_id not in self._views:
            raise ValueError("Unknown linked view.")
        value = _view_title(title)
        if any(key != view_id and item.title.casefold() == value.casefold()
               for key, item in self._views.items()):
            raise ValueError("Linked view names must be unique in this workspace.")
        self._views[view_id].title = value
        return value

    def subscribe(self, view_id, callback):
        if view_id not in self._views:
            raise ValueError("Unknown linked view.")
        self._subscribers[view_id] = callback
        try:
            callback(self.editor_snapshot)
        except Exception as error:
            self.observer_errors[view_id] = str(error)[:500]

    def close_view(self, view_id):
        self._views.pop(view_id)
        self._subscribers.pop(view_id, None)
        self.observer_errors.pop(view_id, None)
        self._bookmarks = {key:value for key,value in self._bookmarks.items()
                           if value.view_id != view_id}
        if self.active_view_id == view_id:
            self.active_view_id = next(iter(self._views), "")

    def activate(self, view_id):
        if view_id not in self._views:
            raise ValueError("Unknown linked view.")
        self.active_view_id = view_id

    def update_view(self, view_id, **values):
        view = self._views[view_id]
        if set(values) - {"geometry", "camera", "display_filters", "render_mode", "lod",
                          "scene_visibility"}:
            raise ValueError("Views cannot replace selection, history, source or journal.")
        candidate = deepcopy(view)
        for key, value in values.items():
            if key == "scene_visibility":
                value = scene_visibility(value)
            setattr(candidate, key, deepcopy(value))
        if candidate.view_type == ViewType.VERTICAL_SLICE:
            SliceGeometry(**candidate.geometry)
        if candidate.view_type == ViewType.AREA_DETAIL:
            AreaGeometry(**candidate.geometry)
        if candidate.render_mode not in ("Classification", "RGB", "Elevation", "Intensity"):
            raise ValueError("Unknown display mode.")
        from .point_appearance import point_appearance
        point_appearance(candidate.lod.get("point_style", "Circular"), candidate.lod.get("point_size", 0))
        self._views[view_id] = candidate

    def accept_editor_snapshot(self, snapshot):
        """Called only by the existing worker/controller, never a renderer."""
        if not snapshot.get("ready"):
            return False
        fingerprint = snapshot.get("source_fingerprint", "")
        if not re.fullmatch("[0-9a-f]{64}", fingerprint):
            raise ValueError("Authoritative worker fingerprint required.")
        session_id = snapshot.get("session_id", "")
        if (fingerprint, session_id) == (self.source_fingerprint, self.session_id) and snapshot.get("revision", -1) < self._editor.get("revision", -1):
            return False
        if (fingerprint, session_id) != (self.source_fingerprint, self.session_id):
            self.global_filters = {}
            self._bookmarks = {}
            for key in list(self._views):
                if self._views[key].view_type != ViewType.OVERVIEW_3D:
                    self.close_view(key)
            for view in self._views.values():
                view.camera, view.display_filters = {}, {}
        self.source_fingerprint = fingerprint
        self.session_id = session_id
        self._editor = deepcopy(snapshot)
        for key, callback in tuple(self._subscribers.items()):
            try:
                callback(self.editor_snapshot)
                self.observer_errors.pop(key, None)
            except Exception as error:
                self.observer_errors[key] = str(error)[:500]
        return True

    def command(self, view_id, action, **values):
        if view_id not in self._views or not self._sink:
            raise ValueError("An attached editor and view are required.")
        if action not in ("select", "clear", "stage", "undo", "redo", "invert",
                          "resize_selection", "export", "save", "cancel"):
            raise ValueError("Unsupported workspace editor command.")
        if self._views[view_id].view_type != ViewType.OVERVIEW_3D and action == "select":
            raise NotImplementedError("Linked selection adapters are not qualified; rendered point indices are never edit addresses.")
        return self._sink(action, **values)

    def to_dict(self):
        return {"schema": self.SCHEMA, "source_fingerprint": self.source_fingerprint,
                "session_id": self.session_id,
                "active_view_id": self.active_view_id, "global_filters": deepcopy(self.global_filters),
                "views": [asdict(view) for view in self._views.values()],
                "bookmarks": [asdict(item) for item in self._bookmarks.values()]}

    @classmethod
    def restore(cls, payload, source_fingerprint, command_sink=None):
        if payload.get("schema") not in (1, cls.SCHEMA) or payload.get("source_fingerprint") != source_fingerprint:
            raise ValueError("Workspace schema or original source fingerprint does not match.")
        result = cls(command_sink)
        result.source_fingerprint = source_fingerprint
        result.session_id = payload.get("session_id", "")
        for value in payload.get("views", []):
            raw = deepcopy(value)
            key = result.register(raw.pop("view_type"), raw.pop("title"),
                                  view_id=raw.pop("view_id"), geometry=raw.pop("geometry"))
            result.update_view(key, **raw)
        for value in payload.get("bookmarks", []):
            raw = deepcopy(value)
            bookmark_id = result.add_bookmark(raw.pop("name"), raw.pop("view_id"),
                raw.pop("camera"), bookmark_id=raw.pop("bookmark_id"))
            expected = ViewType(raw.pop("view_type"))
            if result._bookmarks[bookmark_id].view_type != expected or raw:
                raise ValueError("Saved viewpoint metadata does not match its linked view.")
        result.activate(payload["active_view_id"])
        result.global_filters = deepcopy(payload.get("global_filters", {}))
        if not isinstance(result.global_filters, dict):
            raise ValueError("Workspace global filters must be an object.")
        if "selection_limits" in result.global_filters:
            from .linked_selection import selection_limit_values
            result.global_filters["selection_limits"] = selection_limit_values(
                result.global_filters["selection_limits"])
        if "object_focus_mode" in result.global_filters:
            from .object_focus import normalize_object_focus_mode
            result.global_filters["object_focus_mode"] = normalize_object_focus_mode(
                result.global_filters["object_focus_mode"])
        return result
