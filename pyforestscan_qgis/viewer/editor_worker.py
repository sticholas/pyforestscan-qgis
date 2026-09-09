"""Managed editor process: one source/session, durable journal, value-only IPC."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


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
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity, PointCloudEditSession, AttributeEditOperation
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver, validate_sequence
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
        if session and command.get("view"):
            state = validate_view_state(command["view"])
            session.camera = state["camera"]
            session.visibility["render_mode"] = state["mode"]
            session.filters.update(classes=state["classes"], z=state["height_filter"])
    def visual(item):
        raw = asdict(item)
        return {key: raw[key] for key in ("geometry", "selection_mode", "z_filter", "hag_filter",
                                         "classification_filter", "attribute_filters")}
    def snapshot(*, restored=False, exported=None, highlight=True):
        nonlocal revision
        revision += 1
        edits = []
        history = []
        for op in session.operations:
            if isinstance(op, AttributeEditOperation):
                edits.append({"definitions": [visual(d) for d in op.definitions], "attribute": op.attribute, "value": op.value})
                history.append(f"{op.point_count:,} points: {op.attribute} = {op.value}")
            else:
                x, y, z, xx, yy, zz = op.selection.bounds
                edits.append({"attribute": "Classification", "value": op.classification, "definitions": [{
                    "geometry": [[x,y], [xx,y], [xx,yy], [x,yy], [x,y]],
                    "legacy_bounds": list(op.selection.bounds), "selection_mode": "REPLACE",
                    "classification_filter": list(op.selection.original_classes) or None,
                    "z_filter": [z, zz], "hag_filter": None, "attribute_filters": []}]})
                history.append(f"Legacy region: Classification = {op.classification}")
        atomic_write_json(overlay, {"revision": revision, "edits": edits,
                                   "selection": [visual(d) for d in definitions] if highlight else []})
        emit({"ready": True, "source": session.source.path, "source_fingerprint": session.source.sha256,
              "point_count": point_count, "overlay": str(overlay), "revision": revision,
              "selection": asdict(result) if result else None,
              "can_undo": session.can_undo, "can_redo": session.can_redo,
              "edits": len(session.operations), "autosave": str(autosave),
              "history": list(reversed(history[-20:])),
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
                new_resolver = SelectionResolver(source, cancelled=cancelled.is_set)
                session = candidate or PointCloudEditSession(source, crs_text,
                    tuple(d.strip() for d in metadata["dimensions"].split(",")))
                resolver = new_resolver
                point_count = int(metadata["num_points"])
                definitions, result = (), None
                session.save(autosave)
                snapshot(restored=action == "load")
            elif session is None:
                raise ValueError("Open a local source before editing. EPT edit identity is not yet enabled.")
            else:
                view_update(command)
                if action == "select":
                    resolver._check_source()
                    mode = command.get("mode", "REPLACE")
                    if not definitions and mode == "ADD":
                        mode = "REPLACE"
                    if not definitions and mode == "SUBTRACT":
                        raise ValueError("Select a region before subtracting from it.")
                    state = command.get("view", {})
                    item = SelectionDefinition(uuid4().hex, session.session_id, session.source.sha256,
                        session.source.source_type, command["geometry"], session.source_crs,
                        selection_mode=mode, z_filter=state.get("height_filter"),
                        classification_filter=state.get("classes"))
                    pending = validate_sequence((item,) if mode == "REPLACE" or not definitions else (*definitions, item))
                    progress("Resolving original source points")
                    resolved = resolver.resolve(pending, cancelled=cancelled.is_set,
                                                progress=lambda count: progress("Resolving original source points", count))
                    definitions, result = pending, resolved
                    snapshot()
                elif action == "clear":
                    definitions, result = (), None
                    snapshot()
                elif action == "stage":
                    resolver._check_source()
                    if result is None or command.get("selection_id") != result.selection_id:
                        raise ValueError("Selection changed; resolve and review it before applying an edit.")
                    if not command.get("confirmed") and (result.resolved_point_count > 10_000_000 or
                                                         result.resolved_point_count > point_count * .25):
                        emit({"confirm": True, "selection_id": result.selection_id, "count": result.resolved_point_count,
                              "fraction": result.resolved_point_count / max(point_count, 1), "command": command})
                        continue
                    session.stage_resolved(definitions, result, command["attribute"], command["value"])
                    session.save(autosave)
                    snapshot(highlight=False)
                elif action in ("undo", "redo"):
                    getattr(session, action)()
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
