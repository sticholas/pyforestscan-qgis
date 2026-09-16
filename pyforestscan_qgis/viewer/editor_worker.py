"""Managed editor process: one source/session, durable journal, value-only IPC."""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def visual_definition(item):
    """Value-only renderer projection of authoritative original-source selection."""
    raw = asdict(item)
    return {key: raw[key] for key in ("geometry", "selection_mode", "z_filter", "hag_filter",
        "classification_filter", "attribute_filters", "view_id", "view_name", "clip_geometry",
        "profile_a", "profile_b", "profile_path", "profile_thickness", "profile_geometry", "profile_axis",
        "depth_mode", "circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
        "profile_brush_path", "profile_brush_radius", "profile_brush_tolerance",
        "sphere_center", "sphere_radius", "sphere_axis", "invert_result",
        "profile_line", "profile_line_side")}


@dataclass(frozen=True)
class ViewerPreparationRequest:
    """Minimal request contract for the shared automatic HAG planner."""
    input_path: Path
    source_dimensions: tuple[str, ...]
    crs: str | None = None
    source_coordinate_units: str = ""
    source_units_basis: str = "UNRESOLVED"
    source_point_count: int | None = None
    dtm_path: Path | None = None
    bounds: dict[str, float] | None = None


def _selection_preparation_bounds(result: object) -> dict[str, float] | None:
    """Return the current resolved selection envelope for bounded HAG preparation."""
    values = getattr(result, "bounds", None)
    if not values or len(values) < 5:
        return None
    return {"xmin": float(values[0]), "ymin": float(values[1]),
            "xmax": float(values[3]), "ymax": float(values[4])}


def _active_view_preparation_bounds(view: object) -> dict[str, float] | None:
    """Return a conservative XY support envelope for a linked detail or slice view."""
    if not isinstance(view, dict):
        return None
    geometry = view.get("geometry")
    if not isinstance(geometry, dict):
        return None
    view_type = str(view.get("view_type") or "")
    try:
        if view_type == "AREA_DETAIL":
            shape = str(geometry.get("shape") or "")
            if shape == "POLYGON":
                vertices = tuple(tuple(point) for point in geometry.get("vertices", ()))
                if len(vertices) < 4:
                    return None
                xs, ys = zip(*vertices)
                return _preparation_envelope(min(xs), min(ys), max(xs), max(ys))
            center = tuple(geometry.get("center", ()))
            if len(center) != 2:
                return None
            if shape == "CIRCLE":
                radius = float(geometry.get("radius"))
                return _preparation_envelope(center[0] - radius, center[1] - radius,
                                             center[0] + radius, center[1] + radius)
            width, height = float(geometry.get("width")), float(geometry.get("height"))
            return _preparation_envelope(center[0] - width / 2, center[1] - height / 2,
                                         center[0] + width / 2, center[1] + height / 2)
        if view_type == "VERTICAL_SLICE":
            a, b = tuple(geometry.get("a", ())), tuple(geometry.get("b", ()))
            if len(a) != 2 or len(b) != 2:
                return None
            half_width = float(geometry.get("thickness")) / 2
            return _preparation_envelope(min(a[0], b[0]) - half_width,
                                         min(a[1], b[1]) - half_width,
                                         max(a[0], b[0]) + half_width,
                                         max(a[1], b[1]) + half_width)
    except (TypeError, ValueError):
        return None
    return None


def _active_view_clip_geometry(view: object) -> tuple[tuple[float, float], ...] | None:
    """Return a closed Area Detail boundary for scene-bounded selection inversion."""
    if not isinstance(view, dict) or str(view.get("view_type") or "") != "AREA_DETAIL":
        return None
    geometry = view.get("geometry")
    if not isinstance(geometry, dict):
        return None
    try:
        shape = str(geometry.get("shape") or "")
        if shape == "POLYGON":
            ring = tuple(tuple(map(float, point)) for point in geometry.get("vertices", ()))
        else:
            center = tuple(map(float, geometry.get("center", ())))
            if len(center) != 2:
                return None
            if shape == "CIRCLE":
                radius = float(geometry.get("radius"))
                ring = tuple((center[0] + radius * math.cos(2 * math.pi * index / 48),
                              center[1] + radius * math.sin(2 * math.pi * index / 48))
                             for index in range(49))
            else:
                half_width = float(geometry.get("width")) / 2
                half_height = float(geometry.get("height")) / 2
                ring = ((center[0] - half_width, center[1] - half_height),
                        (center[0] + half_width, center[1] - half_height),
                        (center[0] + half_width, center[1] + half_height),
                        (center[0] - half_width, center[1] + half_height),
                        (center[0] - half_width, center[1] - half_height))
        if len(ring) < 4 or ring[0] != ring[-1] or not all(math.isfinite(value) for point in ring for value in point):
            return None
        return ring
    except (TypeError, ValueError):
        return None


def _preparation_envelope(xmin: object, ymin: object, xmax: object, ymax: object) -> dict[str, float] | None:
    """Validate one bounded XY envelope without accepting camera-space values."""
    values = tuple(float(value) for value in (xmin, ymin, xmax, ymax))
    if not all(math.isfinite(value) for value in values) or values[0] >= values[2] or values[1] >= values[3]:
        return None
    return {"xmin": values[0], "ymin": values[1], "xmax": values[2], "ymax": values[3]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    dll = Path(sys.executable).parent / "Library/bin"
    dll_handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import pdal
    from pyproj import CRS
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from pyforestscan_qgis.core.point_cloud.session import (
        SourceIdentity, PointCloudEditSession, AttributeEditOperation, ObjectIdEditOperation)
    from pyforestscan_qgis.core.point_cloud.selection import (
        SelectionDefinition, SelectionResolver, resized_selection, validate_sequence)
    from pyforestscan_qgis.core.point_cloud.selection_impact import selection_impact
    from pyforestscan_qgis.core.point_cloud.view_session import validate_view_state, session_view_state
    from pyforestscan_qgis.core.point_cloud.export import export_edited

    commands = queue.Queue(maxsize=32)
    cancelled, closing = threading.Event(), threading.Event()
    cancel_generation = [0]
    def emit(value):
        print(json.dumps(value, allow_nan=False), flush=True)
    def read():
        for line in iter(lambda: sys.stdin.readline(2 * 1024 * 1024 + 1), ""):
            if len(line) > 2 * 1024 * 1024:
                closing.set()
                break
            try:
                value = json.loads(line)
                if value.get("action") in ("cancel", "close"):
                    cancel_generation[0] += 1
                    cancelled.set()
                    if value["action"] == "close":
                        closing.set()
                    continue
                value["_cancel_generation"] = cancel_generation[0]
                commands.put_nowait(value)
            except (ValueError, queue.Full):
                emit({"error": "Invalid or excessive editor commands."})
        closing.set()
        cancelled.set()
    threading.Thread(target=read, daemon=True).start()
    session = resolver = result = None
    definitions = ()
    point_count = 0
    revision = 0
    last_progress = 0
    last_stage = None
    autosave = args.folder / "session.json"
    overlay = args.folder / "overlay.json"
    def progress(stage, count=0):
        nonlocal last_progress, last_stage
        now = time.monotonic()
        if now - last_progress > .2 or stage != last_stage:
            emit({"progress": stage, "count": count})
            last_progress, last_stage = now, stage
    def view_update(command):
        if session and command.get("workspace"):
            from pyforestscan_qgis.core.point_cloud.workspace import PointCloudWorkspaceModel
            payload = PointCloudWorkspaceModel.restore(command["workspace"], session.source.sha256).to_dict()
            if payload["session_id"] != session.session_id:
                raise ValueError("Linked views belong to another editing session.")
            session.visibility["linked_workspace"] = payload
        if session and command.get("view"):
            state = validate_view_state(command["view"])
            session.camera = state["camera"]
            session.visibility["render_mode"] = state["mode"]
            session.visibility["quality"] = state["quality"]
            from pyforestscan_qgis.core.point_cloud.view_strategy import session_cache_hint
            hint = session_cache_hint(command.get("view_cache"), session.source.sha256)
            if hint:
                session.visibility["view_cache"] = hint
            session.filters.update(classes=state["classes"], z=state["height_filter"])
    def snapshot(*, restored=False, exported=None, highlight=True):
        nonlocal revision
        revision += 1
        session.visibility["selection_definitions"] = [asdict(item) for item in definitions]
        policy_payload = session.visibility.get("object_id_policy")
        catalog = session.visibility.get("object_catalog")
        if policy_payload and catalog:
            from pyforestscan_qgis.core.point_cloud.object_id_policy import (
                ObjectIdPolicy, next_available_object_id)
            base = dict(policy_payload)
            base.pop("next_available_object_id", None)
            base.pop("allocation_exhausted", None)
            policy = ObjectIdPolicy(**base)
            reserved = [op.value for op in session.operations
                        if isinstance(op, ObjectIdEditOperation) and op.attribute == policy.field]
            try:
                base["next_available_object_id"] = next_available_object_id(
                    catalog["catalog_path"], policy, reserved_ids=reserved)
                base["allocation_exhausted"] = False
            except OverflowError:
                base["next_available_object_id"] = None
                base["allocation_exhausted"] = True
            session.visibility["object_id_policy"] = base
        from pyforestscan_qgis.core.point_cloud.measurement import validate_measurements
        measurements = validate_measurements(session.visibility.get("measurements"),
                                             session.source.sha256)
        session.visibility["measurements"] = measurements
        from pyforestscan_qgis.core.point_cloud.annotation import validate_annotations
        annotations = validate_annotations(session.visibility.get("annotations"),
                                           session.source.sha256)
        session.visibility["annotations"] = annotations
        session.save(autosave)
        reviews = session.visibility.get("object_reviews")
        active = session.visibility.get("active_object")
        current_review = None
        if active:
            from pyforestscan_qgis.core.point_cloud.object_review import object_review_record
            current_review = object_review_record(reviews, session.source.sha256,
                                                  active["field"], active["object_id"])
        edits = []
        history = []
        for op in session.operations:
            if isinstance(op, (AttributeEditOperation, ObjectIdEditOperation)):
                edits.append({"definitions": [visual_definition(d) for d in op.definitions], "attribute": op.attribute, "value": op.value})
                target = f"Object ID {op.attribute}" if isinstance(op, ObjectIdEditOperation) else op.attribute
                history.append(f"{op.point_count:,} points: {target} = {op.value}" +
                               (f" | {op.note}" if op.note else ""))
            else:
                x, y, z, xx, yy, zz = op.selection.bounds
                edits.append({"attribute": "Classification", "value": op.classification, "definitions": [{
                    "geometry": [[x,y], [xx,y], [xx,yy], [x,yy], [x,y]],
                    "legacy_bounds": list(op.selection.bounds), "selection_mode": "REPLACE",
                    "classification_filter": list(op.selection.original_classes) or None,
                    "z_filter": [z, zz], "hag_filter": None, "attribute_filters": []}]})
                history.append(f"Legacy region: Classification = {op.classification}")
        atomic_write_json(overlay, {"revision": revision, "edits": edits,
                                   "selection": [visual_definition(d) for d in definitions] if highlight else []})
        emit({"ready": True, "source": session.source.path, "source_fingerprint": session.source.sha256,
              "source_identity":asdict(session.source), "source_crs":session.source_crs, "dimensions":session.dimensions,
              "session_id": session.session_id,
              "point_count": point_count, "overlay": str(overlay), "revision": revision,
              "selection": asdict(result) if result else None,
              "selection_definitions": [asdict(item) for item in definitions],
              "linked_workspace": session.visibility.get("linked_workspace"),
              "can_undo": session.can_undo, "can_redo": session.can_redo,
              "edits": len(session.operations), "autosave": str(autosave),
              "history": list(reversed(history[-20:])),
              "classification_audit": session.visibility.get("classification_audit"),
              "object_field_discovery": session.visibility.get("object_field_discovery"),
              "object_catalog": session.visibility.get("object_catalog"),
              "effective_object_audit": session.visibility.get("effective_object_audit"),
              "object_reviews": reviews,
              "current_object_review": current_review,
              "measurements": measurements,
              "annotations": annotations,
              "active_object": session.visibility.get("active_object"),
              "object_split_source": session.visibility.get("object_split_source"),
              "object_id_policy": session.visibility.get("object_id_policy"),
              "restored": session_view_state(session) if restored else None, "exported": exported,
              "last_action": action, "last_attribute": command.get("attribute")})
    emit({"started": True})
    while not closing.is_set():
        try:
            command = commands.get(timeout=.1)
        except queue.Empty:
            continue
        if closing.is_set():
            break
        cancelled.clear()
        if command.pop("_cancel_generation") != cancel_generation[0]:
            emit({"error": "Operation cancelled before starting; saved edits are unchanged.", "cancelled": True})
            continue
        action = command.get("action")
        try:
            if action in ("open", "load"):
                progress("Verifying source identity")
                if action == "load":
                    candidate = PointCloudEditSession.load(command["path"], verify_source=False)
                    try:
                        if command.get("source_override"):
                            located = SourceIdentity.capture(command["source_override"], cancelled=cancelled.is_set)
                            if located.sha256 != candidate.source.sha256 or located.source_type != candidate.source.source_type:
                                raise ValueError("The selected file is not the original source of this session.")
                            candidate.source = located
                        else:
                            candidate.source.verify(cancelled=cancelled.is_set)
                    except InterruptedError:
                        raise
                    except (ValueError, OSError) as error:
                        emit({"source_changed": candidate.source.path, "source_unavailable": isinstance(error, OSError),
                              "session_path": command["path"], "error": str(error)})
                        continue
                    if candidate.camera:
                        validate_view_state(session_view_state(candidate))
                    source = candidate.source
                else:
                    source = SourceIdentity.capture(command["source"], cancelled=cancelled.is_set)
                    candidate = None
                kind = "readers.copc" if source.source_type == "COPC" else "readers.las"
                metadata = next(iter(pdal.Pipeline(json.dumps([{"type": kind, "filename": source.path}])).quickinfo.values()))
                srs = metadata.get("srs", {})
                wkt = srs.get("compoundwkt") or srs.get("wkt")
                if wkt:
                    crs = CRS.from_user_input(wkt)
                    authority = crs.to_authority()
                    crs_text = ":".join(authority) if authority else crs.to_wkt()
                else:
                    crs_text = "SOURCE_LOCAL:" + source.sha256
                from pyforestscan_qgis.core.point_cloud.runtime import ViewerRuntimeService
                new_resolver = SelectionResolver(source, cancelled=cancelled.is_set,
                    index_root=ViewerRuntimeService().root/"source-range-index")
                session = candidate or PointCloudEditSession(source, crs_text,
                    tuple(d.strip() for d in metadata["dimensions"].split(",")))
                resolver = new_resolver
                point_count = int(metadata["num_points"])
                definitions, result = (), None
                if action == "load" and session.visibility.get("selection_definitions"):
                    pending = validate_sequence(SelectionDefinition(**item)
                        for item in session.visibility["selection_definitions"])
                    if pending[0].session_id != session.session_id:
                        raise ValueError("Saved selection belongs to a different session.")
                    result = resolver.resolve(pending, cancelled=cancelled.is_set,
                        progress=lambda count: progress("Restoring original source selection", count))
                    definitions = pending
                session.save(autosave)
                snapshot(restored=action == "load")
            elif session is None:
                raise ValueError("Open a local source before editing. EPT edit identity is not yet enabled.")
            else:
                view_update(command)
                if action == "workspace":
                    session.save(autosave)
                    emit({"workspace_saved": True})
                elif action == "select":
                    resolver._check_source()
                    mode = command.get("mode", "REPLACE")
                    if not definitions and mode == "ADD":
                        mode = "REPLACE"
                    if not definitions and mode == "SUBTRACT":
                        raise ValueError("Select a region before subtracting from it.")
                    state = command.get("view", {})
                    constraints = command.get("constraints")
                    if constraints is None:
                        constraints = {"z_filter": state.get("height_filter"),
                                       "classification_filter": state.get("classes")}
                    allowed = {"view_id", "view_name", "clip_geometry", "profile_a", "profile_b", "profile_path",
                               "profile_thickness", "profile_geometry", "profile_axis", "depth_mode",
                               "z_filter", "hag_filter", "classification_filter", "attribute_filters"}
                    if not isinstance(constraints, dict) or set(constraints) - allowed:
                        raise ValueError("Unsupported linked selection constraints.")
                    primitive = {}
                    if "circle_center" in command or "circle_radius" in command:
                        primitive = {"circle_center": command.get("circle_center"),
                                     "circle_radius": command.get("circle_radius")}
                    if "brush_path" in command or "brush_radius" in command or "brush_tolerance" in command:
                        if primitive:
                            raise ValueError("Selection has competing spatial primitives.")
                        primitive = {"brush_path": command.get("brush_path"),
                                     "brush_radius": command.get("brush_radius"),
                                     "brush_tolerance": command.get("brush_tolerance", 0)}
                    if ("profile_brush_path" in command or "profile_brush_radius" in command
                            or "profile_brush_tolerance" in command):
                        if primitive:
                            raise ValueError("Selection has competing spatial primitives.")
                        primitive = {"profile_brush_path": command.get("profile_brush_path"),
                                     "profile_brush_radius": command.get("profile_brush_radius"),
                                     "profile_brush_tolerance": command.get(
                                         "profile_brush_tolerance", 0)}
                    if "sphere_center" in command or "sphere_radius" in command:
                        if primitive:
                            raise ValueError("Selection has competing spatial primitives.")
                        primitive = {"sphere_center": command.get("sphere_center"),
                                     "sphere_radius": command.get("sphere_radius"),
                                     "sphere_axis": command.get("sphere_axis", "Z")}
                    if "profile_line" in command or "profile_line_side" in command:
                        if primitive:
                            raise ValueError("Selection has competing spatial primitives.")
                        primitive = {"profile_line": command.get("profile_line"),
                                     "profile_line_side": command.get("profile_line_side")}
                    item = SelectionDefinition(uuid4().hex, session.session_id, session.source.sha256,
                        session.source.source_type, command["geometry"], session.source_crs,
                        selection_mode=mode, **constraints, **primitive)
                    pending = validate_sequence((item,) if mode == "REPLACE" or not definitions else (*definitions, item))
                    progress("Resolving original source points")
                    resolved = resolver.resolve(pending, cancelled=cancelled.is_set,
                                                progress=lambda count: progress("Resolving original source points", count))
                    definitions, result = pending, resolved
                    session.visibility.pop("active_object", None)
                    snapshot()
                elif action == "update_selection_filters":
                    if not definitions:
                        raise ValueError("There is no current selection to update.")
                    z_filter = command.get("z_filter")
                    hag_filter = command.get("hag_filter")
                    pending = tuple(replace(item, z_filter=z_filter, hag_filter=hag_filter)
                                    for item in definitions)
                    pending = validate_sequence(pending)
                    progress("Updating current selection height range")
                    resolved = resolver.resolve(
                        pending, cancelled=cancelled.is_set,
                        progress=lambda count: progress("Updating current selection height range", count))
                    definitions, result = pending, resolved
                    session.visibility.pop("active_object", None)
                    snapshot()
                elif action == "prepare_hag":
                    if "HeightAboveGround" in session.dimensions:
                        emit({"hag_prepared": session.source.path, "hag_reused": True,
                              "message": "Height Above Ground is already available."})
                        continue
                    preparation_bounds = (_selection_preparation_bounds(result)
                                          or _active_view_preparation_bounds(command.get("active_view")))
                    if preparation_bounds is None:
                        raise ValueError(
                            "Open an Area Detail or Vertical Slice, or resolve a selection before preparing HAG. "
                            "Whole-source preparation was not started.")
                    from pyforestscan_qgis.backend_runner.pbm_lidar_preparation import prepare_request_source
                    from pyforestscan_qgis.core.source_coordinate_units import assess_source_coordinate_units
                    crs_value = None if session.source_crs.startswith("SOURCE_LOCAL:") else session.source_crs
                    units = assess_source_coordinate_units(
                        crs_value, command.get("source_coordinate_units"))
                    unit_basis = command.get("source_units_basis") or units.unit_basis
                    request = ViewerPreparationRequest(
                        input_path=Path(session.source.path), source_dimensions=tuple(session.dimensions),
                        crs=crs_value, source_coordinate_units=units.units.value,
                        source_units_basis=unit_basis, source_point_count=None,
                        bounds=preparation_bounds)
                    spec = type("ViewerHagSpec", (), {
                        "product": "viewer_hag", "requested_products": ("chm",),
                        "run_folder": args.folder / "hag-preparation",
                        "job_id": "viewer-hag-" + session.source.sha256[:12]})()
                    progress("Preparing Height Above Ground for bounded viewer extent")
                    prepared = prepare_request_source(spec, request,
                        progress=lambda message: progress(str(message)),
                        preparation_bounds=preparation_bounds)
                    if prepared is None:
                        raise ValueError("Automatic HAG preparation did not produce a derivative.")
                    artifact = Path(prepared.request.input_path)
                    if not artifact.is_file():
                        raise ValueError("Automatic HAG preparation completed without a readable derivative.")
                    emit({"hag_prepared": str(artifact), "hag_reused": prepared.reused,
                          "hag_provenance": str(prepared.provenance_path),
                          "message": "Prepared HAG derivative is ready; original source unchanged."})
                elif action == "clear":
                    definitions, result = (), None
                    session.visibility.pop("active_object", None)
                    snapshot()
                elif action == "invert":
                    if not definitions:
                        raise ValueError("Resolve a source selection before inverting it.")
                    clip_geometry = _active_view_clip_geometry(command.get("active_view"))
                    pending = (*definitions[:-1], replace(definitions[-1],
                        invert_result=not definitions[-1].invert_result,
                        clip_geometry=clip_geometry or definitions[-1].clip_geometry))
                    progress("Resolving inverted selection inside active view" if clip_geometry else
                             "Resolving inverted original-source selection")
                    resolved = resolver.resolve(pending, cancelled=cancelled.is_set,
                        progress=lambda count: progress("Resolving inverted original-source selection", count))
                    definitions, result = pending, resolved
                    session.visibility.pop("active_object", None)
                    snapshot()
                elif action == "resize_selection":
                    pending = resized_selection(definitions, command.get("distance"),
                                                selection_id=uuid4().hex)
                    progress("Resolving resized original-source selection")
                    resolved = resolver.resolve(pending, cancelled=cancelled.is_set,
                        progress=lambda count: progress("Resolving resized original-source selection", count))
                    definitions, result = pending, resolved
                    session.visibility.pop("active_object", None)
                    snapshot()
                elif action == "stage":
                    resolver._check_source()
                    if result is None or command.get("selection_id") != result.selection_id:
                        raise ValueError("Selection changed; resolve and review it before applying an edit.")
                    impact = selection_impact(result.resolved_point_count, point_count)
                    if not command.get("confirmed") and impact.requires_confirmation:
                        emit({"confirm": True, "selection_id": result.selection_id, "count": result.resolved_point_count,
                              "fraction": impact.fraction, "impact": impact.message, "command": command})
                        continue
                    origin = definitions[-1].view_name
                    session.stage_resolved(definitions, result, command["attribute"], command["value"],
                                           note=("View: " + origin) if origin else "")
                    session.visibility.pop("classification_audit", None)
                    session.visibility.pop("effective_object_audit", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "stage_object_id":
                    from pyforestscan_qgis.core.point_cloud.object_id_policy import ObjectIdPolicy
                    resolver._check_source()
                    if result is None or command.get("selection_id") != result.selection_id:
                        raise ValueError("Selection changed; resolve and review it before applying an object edit.")
                    impact = selection_impact(result.resolved_point_count, point_count)
                    if not command.get("confirmed") and impact.requires_confirmation:
                        emit({"confirm": True, "selection_id":result.selection_id,
                              "count":result.resolved_point_count, "fraction":impact.fraction,
                              "impact":impact.message, "command":command, "edit_kind":"OBJECT_ID"})
                        continue
                    payload = dict(session.visibility.get("object_id_policy") or {})
                    payload.pop("next_available_object_id", None)
                    payload.pop("allocation_exhausted", None)
                    policy = ObjectIdPolicy(**payload)
                    try:
                        value = int(str(command.get("value", "")), 10)
                    except ValueError:
                        raise ValueError("Target object ID must be an integer.")
                    session.stage_object_id(definitions, result, policy, value,
                        note=f"Object field {policy.field}")
                    session.visibility.pop("active_object", None)
                    session.visibility.pop("effective_object_audit", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action in ("undo", "redo"):
                    changed = getattr(session, action)()
                    if changed:
                        session.visibility.pop("classification_audit", None)
                        session.visibility.pop("effective_object_audit", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "classification_audit":
                    from pyforestscan_qgis.core.point_cloud.classification_audit import audit_source_classifications
                    progress("Auditing original and staged classifications")
                    report = audit_source_classifications(session.source, session.operations, point_count,
                        cancelled=cancelled.is_set,
                        progress=lambda count: progress("Auditing original and staged classifications", count))
                    session.visibility["classification_audit"] = report
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "discover_object_fields":
                    from pyforestscan_qgis.core.point_cloud.object_fields import discover_source_object_fields
                    progress("Discovering object and segment fields")
                    report = discover_source_object_fields(session.source, point_count,
                        cancelled=cancelled.is_set,
                        progress=lambda count: progress("Discovering object and segment fields", count))
                    session.visibility["object_field_discovery"] = report
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "build_object_catalog":
                    from pyforestscan_qgis.core.point_cloud.object_catalog import build_source_object_catalog
                    discovery = session.visibility.get("object_field_discovery") or {}
                    candidates = {item["name"] for item in discovery.get("candidate_fields", [])}
                    field = command.get("field")
                    if field not in candidates:
                        raise ValueError("Discover and choose a current categorical object-field candidate first.")
                    token = hashlib.sha256(field.encode("utf-8")).hexdigest()[:12]
                    destination = args.folder / f"objects-{token}.sqlite"
                    progress(f"Cataloging exact {field} objects")
                    report = build_source_object_catalog(session.source, point_count, field, destination,
                        cancelled=cancelled.is_set,
                        progress=lambda count: progress(f"Cataloging exact {field} objects", count))
                    session.visibility["object_catalog"] = report
                    session.visibility.pop("effective_object_audit", None)
                    session.visibility.pop("active_object", None)
                    session.visibility.pop("object_split_source", None)
                    session.visibility.pop("object_id_policy", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "configure_object_id_policy":
                    from pyforestscan_qgis.core.point_cloud.object_id_policy import (
                        create_object_id_policy, next_available_object_id)
                    catalog = session.visibility.get("object_catalog")
                    if not catalog:
                        raise ValueError("Build an exact object catalog before defining ID semantics.")
                    try:
                        unassigned_id = int(str(command.get("unassigned_id", "")), 10)
                    except ValueError:
                        raise ValueError("Unassigned object ID must be an integer.")
                    policy = create_object_id_policy(catalog, unassigned_id)
                    next_id = next_available_object_id(catalog["catalog_path"], policy)
                    session.visibility["object_id_policy"] = {
                        **policy.to_dict(), "next_available_object_id":next_id,
                        "allocation_exhausted":False}
                    session.visibility.pop("object_split_source", None)
                    session.visibility.pop("effective_object_audit", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action in ("select_object", "neighbor_object"):
                    from pyforestscan_qgis.core.point_cloud.object_catalog import (
                        catalog_neighbor, catalog_object, object_selection_definition)
                    catalog = session.visibility.get("object_catalog")
                    if not catalog:
                        raise ValueError("Build an exact object catalog before selecting an object.")
                    field = catalog["field"]
                    path = catalog["catalog_path"]
                    if action == "neighbor_object":
                        active = session.visibility.get("active_object")
                        if not active or active.get("field") != field:
                            raise ValueError("Select an object before moving to its neighbor.")
                        row = catalog_neighbor(path, int(active["object_id"]), int(command.get("direction", 0)),
                            source_sha256=session.source.sha256, field=field)
                        if row is None:
                            raise ValueError("There is no object in that direction.")
                    else:
                        try:
                            object_id = int(str(command.get("object_id", "")), 10)
                        except ValueError:
                            raise ValueError("Object ID must be an integer.")
                        row = catalog_object(path, object_id,
                            source_sha256=session.source.sha256, field=field)
                        if row is None:
                            raise ValueError(f"Object ID {object_id} is not present in {field}.")
                    item = object_selection_definition(session, field, row)
                    resolver._check_source()
                    progress(f"Resolving {field} object {row['object_id']}")
                    resolved = resolver.resolve((item,), cancelled=cancelled.is_set,
                        progress=lambda count: progress(f"Resolving {field} object {row['object_id']}", count))
                    if resolved.resolved_point_count != row["point_count"]:
                        raise ValueError("Object catalog and authoritative selection counts differ; rebuild the catalog.")
                    definitions, result = (item,), resolved
                    session.visibility["active_object"] = {
                        "field":field, **row, "selection_id":resolved.selection_id}
                    session.visibility.pop("object_split_source", None)
                    session.save(autosave)
                    snapshot()
                elif action == "begin_object_split":
                    from pyforestscan_qgis.core.point_cloud.object_operations import begin_object_split
                    split = begin_object_split(session.source.sha256,
                        session.visibility.get("object_catalog"),
                        session.visibility.get("active_object"), result)
                    policy = session.visibility.get("object_id_policy") or {}
                    if policy.get("field") != split.field:
                        raise ValueError("Confirm object ID semantics for this field before splitting.")
                    session.visibility["object_split_source"] = split.to_dict()
                    definitions, result = (), None
                    session.visibility.pop("active_object", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "cancel_object_split":
                    session.visibility.pop("object_split_source", None)
                    session.save(autosave)
                    snapshot()
                elif action == "split_object":
                    from pyforestscan_qgis.core.point_cloud.object_id_policy import (
                        ObjectIdPolicy, next_available_object_id)
                    from pyforestscan_qgis.core.point_cloud.object_operations import (
                        ObjectSplitSource, restrict_selection_to_object, validate_split_count)
                    resolver._check_source()
                    if result is None or command.get("selection_id") != result.selection_id:
                        raise ValueError("Selection changed; resolve the split portion again.")
                    split_payload = session.visibility.get("object_split_source")
                    if not split_payload:
                        raise ValueError("Choose an exact parent object before resolving a split portion.")
                    split = ObjectSplitSource(**split_payload)
                    payload = dict(session.visibility.get("object_id_policy") or {})
                    payload.pop("next_available_object_id", None)
                    payload.pop("allocation_exhausted", None)
                    policy = ObjectIdPolicy(**payload)
                    if policy.field != split.field:
                        raise ValueError("Split parent and object ID policy use different fields.")
                    impact = selection_impact(result.resolved_point_count, point_count)
                    if not command.get("confirmed") and impact.requires_confirmation:
                        emit({"confirm":True, "selection_id":result.selection_id,
                              "count":result.resolved_point_count, "fraction":impact.fraction,
                              "impact":impact.message, "command":command, "edit_kind":"OBJECT_ID"})
                        continue
                    pending = restrict_selection_to_object(definitions, split,
                                                           selection_id=uuid4().hex)
                    progress(f"Resolving split portion of {split.field} object {split.object_id}")
                    resolved = resolver.resolve(pending, cancelled=cancelled.is_set,
                        progress=lambda count: progress(
                            f"Resolving split portion of {split.field} object {split.object_id}", count))
                    validate_split_count(split, resolved.resolved_point_count)
                    catalog = session.visibility.get("object_catalog") or {}
                    reserved = [op.value for op in session.operations
                        if isinstance(op, ObjectIdEditOperation) and op.attribute == policy.field]
                    new_id = next_available_object_id(catalog["catalog_path"], policy,
                                                      reserved_ids=reserved)
                    session.stage_object_id(pending, resolved, policy, new_id,
                        note=f"Split {policy.field} object {split.object_id} into new object {new_id}")
                    definitions, result = pending, resolved
                    session.visibility.pop("active_object", None)
                    session.visibility.pop("object_split_source", None)
                    session.visibility.pop("effective_object_audit", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "merge_object":
                    from pyforestscan_qgis.core.point_cloud.object_catalog import catalog_object
                    from pyforestscan_qgis.core.point_cloud.object_id_policy import ObjectIdPolicy
                    from pyforestscan_qgis.core.point_cloud.object_operations import validate_merge_target
                    resolver._check_source()
                    active = session.visibility.get("active_object") or {}
                    if (result is None or command.get("selection_id") != result.selection_id
                            or active.get("selection_id") != result.selection_id
                            or active.get("point_count") != result.resolved_point_count):
                        raise ValueError("Select the exact source object again before merging it.")
                    payload = dict(session.visibility.get("object_id_policy") or {})
                    payload.pop("next_available_object_id", None)
                    payload.pop("allocation_exhausted", None)
                    policy = ObjectIdPolicy(**payload)
                    catalog = session.visibility.get("object_catalog") or {}
                    if not catalog.get("catalog_path"):
                        raise ValueError("Build a current exact object catalog before merging.")
                    if policy.field != active.get("field"):
                        raise ValueError("Merge selection and object ID policy use different fields.")
                    try:
                        requested = int(str(command.get("target_object_id", "")), 10)
                    except ValueError:
                        raise ValueError("Merge target object ID must be an integer.")
                    target = catalog_object(catalog["catalog_path"], requested,
                        source_sha256=session.source.sha256, field=policy.field)
                    target_id = validate_merge_target(catalog, active, target)
                    impact = selection_impact(result.resolved_point_count, point_count)
                    if not command.get("confirmed") and impact.requires_confirmation:
                        emit({"confirm":True, "selection_id":result.selection_id,
                              "count":result.resolved_point_count, "fraction":impact.fraction,
                              "impact":impact.message, "command":command, "edit_kind":"OBJECT_ID"})
                        continue
                    session.stage_object_id(definitions, result, policy, target_id,
                        note=f"Merge {policy.field} object {active['object_id']} into {target_id}")
                    session.visibility.pop("active_object", None)
                    session.visibility.pop("object_split_source", None)
                    session.visibility.pop("effective_object_audit", None)
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "effective_object_audit":
                    from pyforestscan_qgis.core.point_cloud.object_audit import audit_source_objects
                    from pyforestscan_qgis.core.point_cloud.object_id_policy import ObjectIdPolicy
                    payload = dict(session.visibility.get("object_id_policy") or {})
                    payload.pop("next_available_object_id", None)
                    payload.pop("allocation_exhausted", None)
                    policy = ObjectIdPolicy(**payload)
                    catalog = session.visibility.get("object_catalog") or {}
                    if (catalog.get("source_sha256") != session.source.sha256
                            or catalog.get("field") != policy.field):
                        raise ValueError("Build a current exact catalog and confirm object ID semantics first.")
                    token = hashlib.sha256(policy.field.encode("utf-8")).hexdigest()[:12]
                    destination = args.folder/f"effective-objects-{token}.sqlite"
                    progress(f"Auditing effective {policy.field} membership")
                    report = audit_source_objects(session.source, session.operations, point_count,
                        policy.field, destination, policy.unassigned_id,
                        cancelled=cancelled.is_set,
                        progress=lambda count: progress(
                            f"Auditing effective {policy.field} membership", count))
                    session.visibility["effective_object_audit"] = report
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "set_object_review":
                    from pyforestscan_qgis.core.point_cloud.object_review import update_object_review
                    active = session.visibility.get("active_object") or {}
                    catalog = session.visibility.get("object_catalog") or {}
                    if (result is None or command.get("selection_id") != result.selection_id
                            or active.get("selection_id") != result.selection_id
                            or active.get("field") != catalog.get("field")
                            or catalog.get("source_sha256") != session.source.sha256):
                        raise ValueError("Select the exact catalog object before updating its review.")
                    keyword = {}
                    if "reviewed" in command:
                        keyword["reviewed"] = command["reviewed"]
                    if "note" in command:
                        keyword["note"] = command["note"]
                    session.visibility["object_reviews"] = update_object_review(
                        session.visibility.get("object_reviews"), session.source.sha256,
                        active["field"], active["object_id"], **keyword)
                    session.save(autosave)
                    snapshot()
                elif action == "add_measurement":
                    from pyforestscan_qgis.core.point_cloud.measurement import (
                        MAX_MEASUREMENTS, resolve_source_measurement, validate_measurements)
                    current = validate_measurements(session.visibility.get("measurements"),
                                                    session.source.sha256)
                    if len(current) >= MAX_MEASUREMENTS:
                        raise ValueError(f"One session supports at most {MAX_MEASUREMENTS:,} measurements.")
                    progress("Resolving original source measurement anchors")
                    measurement = resolve_source_measurement(session.source, point_count,
                        command.get("points") or (), session.source_crs,
                        pdal_module=pdal, crs_type=CRS, cancelled=cancelled.is_set,
                        progress=lambda count: progress(
                            "Resolving original source measurement anchors", count))
                    session.visibility["measurements"] = [*current, measurement.to_dict()]
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "add_area_measurement":
                    from pyforestscan_qgis.core.point_cloud.measurement import (
                        MAX_MEASUREMENTS, create_area_measurement,
                        measurement_unit_context, validate_measurements)
                    current = validate_measurements(session.visibility.get("measurements"),
                                                    session.source.sha256)
                    if len(current) >= MAX_MEASUREMENTS:
                        raise ValueError(f"One session supports at most {MAX_MEASUREMENTS:,} measurements.")
                    progress("Verifying source and planar area")
                    session.source.verify(cancelled=cancelled.is_set)
                    horizontal, _vertical, warning = measurement_unit_context(
                        session.source_crs, CRS)
                    measurement = create_area_measurement(session.source.sha256,
                        session.source_crs, command.get("geometry") or (),
                        horizontal_unit=horizontal,
                        display_elevation=command.get("display_elevation"),
                        unit_warning=warning)
                    session.visibility["measurements"] = [*current, measurement.to_dict()]
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "add_profile_measurement":
                    from pyforestscan_qgis.core.point_cloud.measurement import (
                        MAX_MEASUREMENTS, resolve_source_profile_measurement,
                        validate_measurements)
                    current = validate_measurements(session.visibility.get("measurements"),
                                                    session.source.sha256)
                    if len(current) >= MAX_MEASUREMENTS:
                        raise ValueError(f"One session supports at most {MAX_MEASUREMENTS:,} measurements.")
                    progress("Resolving original source profile anchors")
                    measurement = resolve_source_profile_measurement(session.source,
                        point_count, command.get("points") or (), session.source_crs,
                        command.get("profile_geometry") or {}, command.get("view_id") or "",
                        command.get("view_name") or "", pdal_module=pdal, crs_type=CRS,
                        cancelled=cancelled.is_set,
                        progress=lambda count: progress(
                            "Resolving original source profile anchors",count),
                        purpose=command.get("purpose") or "CROSS_SECTION")
                    session.visibility["measurements"] = [*current,measurement.to_dict()]
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "clear_measurements":
                    session.visibility["measurements"] = []
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "add_annotation":
                    from pyforestscan_qgis.core.point_cloud.annotation import (
                        MAX_ANNOTATIONS, resolve_source_annotation,
                        resolve_source_profile_annotation,
                        validate_annotations)
                    current = validate_annotations(session.visibility.get("annotations"),
                                                   session.source.sha256)
                    if len(current) >= MAX_ANNOTATIONS:
                        raise ValueError(
                            f"One session supports at most {MAX_ANNOTATIONS:,} annotations.")
                    progress("Resolving original source annotation anchor")
                    resolver_function = (resolve_source_profile_annotation
                        if command.get("profile_geometry") else resolve_source_annotation)
                    args = [session.source, point_count, command.get("point") or (),
                            session.source_crs]
                    if command.get("profile_geometry"):
                        args.append(command["profile_geometry"])
                    annotation = resolver_function(*args,
                        command.get("title") or "", command.get("note") or "",
                        pdal_module=pdal, cancelled=cancelled.is_set,
                        progress=lambda count: progress(
                            "Resolving original source annotation anchor", count))
                    session.visibility["annotations"] = [*current, annotation.to_dict()]
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "update_annotation":
                    from pyforestscan_qgis.core.point_cloud.annotation import replace_annotation
                    session.visibility["annotations"] = replace_annotation(
                        session.visibility.get("annotations"), session.source.sha256,
                        command.get("annotation_id") or "", title=command.get("title"),
                        note=command.get("note"))
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "remove_annotation":
                    from pyforestscan_qgis.core.point_cloud.annotation import remove_annotation
                    session.visibility["annotations"] = remove_annotation(
                        session.visibility.get("annotations"), session.source.sha256,
                        command.get("annotation_id") or "")
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "clear_annotations":
                    session.visibility["annotations"] = []
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action == "save":
                    progress("Verifying and saving session")
                    session.source.verify(cancelled=cancelled.is_set)
                    session.save(command["path"])
                    session.save(autosave)
                    snapshot(highlight=False)
                    emit({"saved": command["path"]})
                elif action == "export":
                    session.save(autosave)
                    report = export_edited(session, command["path"], cancelled=cancelled.is_set, progress=progress)
                    session.export_history.append(report)
                    session.save(autosave)
                    snapshot(exported=report, highlight=False)
                elif action == "verify_handoff":
                    report = next((item for item in reversed(session.export_history)
                                   if item["export_id"] == command.get("export_id")), None)
                    if not report:
                        raise ValueError("Export is not recorded in this session.")
                    progress("Verifying exported input")
                    identity = SourceIdentity.capture(report["output"], cancelled=cancelled.is_set)
                    if identity.sha256 != report["output_sha256"]:
                        raise ValueError("Export changed after validation. Export a new file before using it in Process.")
                    emit({"handoff_ready": report})
                else:
                    raise ValueError("Unknown editor action.")
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            emit({"error": str(error), "action": action, "cancelled": isinstance(error, InterruptedError),
                  "autosave": str(autosave) if autosave.exists() else None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
