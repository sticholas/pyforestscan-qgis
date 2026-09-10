"""Disk-backed effective object accounting through the active edit journal."""
from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
from time import monotonic
from uuid import uuid4

from .edit_plan import EditExecutionPlan


CHUNK_SIZE = 65_536
_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _field_name(field):
    if not isinstance(field, str) or not _FIELD.fullmatch(field):
        raise ValueError("Object audit requires a valid source object field.")
    return field


def _rows(values, np):
    raw = np.asarray(values).reshape(-1)
    if raw.dtype.kind not in "iu":
        raise ValueError("Effective object auditing requires an integer-backed object field.")
    identifiers, counts = np.unique(raw, return_counts=True)
    result = []
    for identifier, count in zip(identifiers, counts):
        value = int(identifier)
        if not -(2**63) <= value <= 2**63-1:
            raise ValueError("Object identifier exceeds the supported signed 64-bit range.")
        result.append((value, int(count)))
    return result


def effective_object_audit_report(path):
    database = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(database)) as connection:
        metadata = {key: json.loads(value) for key, value in
                    connection.execute("SELECT key, value FROM metadata")}
        source_objects, effective_objects = connection.execute(
            "SELECT SUM(source_count>0), SUM(effective_count>0) FROM counts").fetchone()
        largest = connection.execute(
            "SELECT object_id, effective_count FROM counts WHERE effective_count>0 "
            "ORDER BY effective_count DESC, object_id LIMIT 10").fetchall()
        unassigned = connection.execute(
            "SELECT source_count, effective_count FROM counts WHERE object_id=?",
            (metadata["unassigned_id"],)).fetchone() or (0, 0)
    return {
        "status":"READY",
        "audit_path":str(database),
        **metadata,
        "source_object_count":int(source_objects or 0),
        "effective_object_count":int(effective_objects or 0),
        "source_unassigned_count":int(unassigned[0]),
        "effective_unassigned_count":int(unassigned[1]),
        "largest_effective_objects":[[int(identifier), int(count)]
                                     for identifier, count in largest],
        "exact":True,
        "bounded_memory":True,
        "chunk_size":CHUNK_SIZE,
        "modifies_source_or_journal":False,
    }


def audit_object_chunks(chunks, operations, expected_points, field, destination,
                        source_sha256, unassigned_id, *,
                        cancelled=lambda: False, progress=lambda count: None):
    """Replay edits chunkwise and atomically aggregate source/effective IDs."""
    if type(expected_points) is not int or expected_points < 0:
        raise ValueError("Expected source point count must be a non-negative integer.")
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("Object audit requires the source content fingerprint.")
    if type(unassigned_id) is not int:
        raise ValueError("Object audit requires the confirmed integer unassigned value.")
    field = _field_name(field)
    import numpy as np

    operations = tuple(operations)
    plan = EditExecutionPlan(operations) if operations else None
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".building-" + uuid4().hex)
    connection = None
    started = monotonic()
    scanned = effective_points = changed = removed = 0
    try:
        connection = sqlite3.connect(temporary)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE counts (object_id INTEGER PRIMARY KEY, "
                           "source_count INTEGER NOT NULL DEFAULT 0, "
                           "effective_count INTEGER NOT NULL DEFAULT 0)")
        source_statement = """INSERT INTO counts(object_id,source_count) VALUES (?,?)
            ON CONFLICT(object_id) DO UPDATE SET source_count=source_count+excluded.source_count"""
        effective_statement = """INSERT INTO counts(object_id,effective_count) VALUES (?,?)
            ON CONFLICT(object_id) DO UPDATE SET effective_count=effective_count+excluded.effective_count"""
        for original in chunks:
            if cancelled():
                raise InterruptedError("Object audit cancelled; source, journal and prior audit are unchanged.")
            if field not in (original.dtype.names or ()):
                raise ValueError(f"Source does not contain object field {field}.")
            if plan is None:
                edited = original.copy()
                removed_mask = np.zeros(len(original), dtype=bool)
            else:
                edited, removed_mask = plan.apply(original)
            kept = ~removed_mask
            with connection:
                connection.executemany(source_statement, _rows(original[field], np))
                connection.executemany(effective_statement, _rows(edited[field][kept], np))
            changed += int(((edited[field] != original[field]) & kept).sum())
            removed += int(removed_mask.sum())
            scanned += len(original)
            effective_points += int(kept.sum())
            progress(scanned)
        if scanned != expected_points:
            raise ValueError("Object audit source count differs from the verified header.")
        metadata = {
            "audit_id":uuid4().hex,
            "source_sha256":source_sha256,
            "field":field,
            "unassigned_id":unassigned_id,
            "source_point_count":scanned,
            "effective_point_count":effective_points,
            "object_id_changed":changed,
            "removed_on_export":removed,
            "staged_operations":len(operations),
            "duration_seconds":monotonic()-started,
            "addressing":"FULL_RESOLUTION_ORIGINAL_SOURCE_SEQUENTIAL_AUDIT",
        }
        with connection:
            connection.executemany("INSERT INTO metadata VALUES (?,?)",
                ((key, json.dumps(value, allow_nan=False)) for key, value in metadata.items()))
        connection.close()
        connection = None
        os.replace(temporary, destination)
        return effective_object_audit_report(destination)
    finally:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)


def audit_source_objects(source, operations, expected_points, field, destination,
                         unassigned_id, *, pdal_module=None,
                         cancelled=lambda: False, progress=lambda count: None):
    """Verify and stream one local source without materializing its objects."""
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    source.verify(cancelled=cancelled)
    reader = {"type":"readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename":source.path}
    chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=CHUNK_SIZE, prefetch=0)
    report = audit_object_chunks(chunks, operations, expected_points, field, destination,
                                 source.sha256, unassigned_id,
                                 cancelled=cancelled, progress=progress)
    source.verify(cancelled=cancelled)
    return report


def effective_object_audit_summary(report):
    if not isinstance(report, dict) or report.get("status") != "READY" or not report.get("exact"):
        raise ValueError("Invalid effective object audit report.")
    return (f"Effective object audit: {report['field']} | "
            f"{report['effective_object_count']:,} objects | "
            f"{report['object_id_changed']:,} staged membership changes | "
            f"{report['effective_unassigned_count']:,} unassigned")
