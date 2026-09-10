"""Disk-backed exact catalogs for one discovered categorical source dimension."""
from __future__ import annotations

from contextlib import closing
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from time import monotonic
from uuid import uuid4

from .object_fields import CHUNK_SIZE


MIN_INT64 = -(2 ** 63)
MAX_INT64 = 2 ** 63 - 1


def _validated_field(field):
    if (not isinstance(field, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field)
            or field in ("X", "Y", "Z", "Classification", "HeightAboveGround")):
        raise ValueError("Object catalog requires a selectable nonstandard source dimension.")
    return field


def _chunk_rows(chunk, field, np):
    names = chunk.dtype.names or ()
    if field not in names or not all(name in names for name in ("X", "Y", "Z")):
        raise ValueError(f"Source does not contain catalog field {field} and XYZ coordinates.")
    raw = np.asarray(chunk[field]).reshape(-1)
    kind = raw.dtype.kind
    if kind not in "biuf":
        raise ValueError("Object catalog fields must contain integer-like numeric values.")
    if kind == "f":
        valid = np.isfinite(raw)
        values = raw[valid]
        if len(values) and not np.allclose(values, np.rint(values), rtol=0, atol=1e-7):
            raise ValueError("Object catalog field contains non-integer values.")
    else:
        valid = np.ones(len(raw), dtype=bool)
        values = raw
    missing = int(len(raw) - len(values))
    if not len(values):
        return (), missing
    minimum_id = int(np.rint(values.min())) if kind == "f" else int(values.min())
    maximum_id = int(np.rint(values.max())) if kind == "f" else int(values.max())
    if minimum_id < MIN_INT64 or maximum_id > MAX_INT64:
        raise ValueError("Object identifiers exceed the supported signed 64-bit range.")
    ids = values.astype(np.int64, copy=False)
    coordinates = []
    for name in ("X", "Y", "Z"):
        coordinate = np.asarray(chunk[name]).reshape(-1)[valid]
        if not np.isfinite(coordinate).all():
            raise ValueError("Object catalog requires finite XYZ coordinates.")
        coordinates.append(coordinate)
    order = np.argsort(ids, kind="stable")
    ordered_ids = ids[order]
    starts = np.r_[0, np.flatnonzero(ordered_ids[1:] != ordered_ids[:-1]) + 1]
    ends = np.r_[starts[1:], len(ordered_ids)]
    ordered_coordinates = [coordinate[order] for coordinate in coordinates]
    minimums = [np.minimum.reduceat(coordinate, starts) for coordinate in ordered_coordinates]
    maximums = [np.maximum.reduceat(coordinate, starts) for coordinate in ordered_coordinates]
    rows = []
    for index, start in enumerate(starts):
        rows.append((int(ordered_ids[start]), int(ends[index] - start),
                     float(minimums[0][index]), float(minimums[1][index]), float(minimums[2][index]),
                     float(maximums[0][index]), float(maximums[1][index]), float(maximums[2][index])))
    return rows, missing


def _read_metadata(connection):
    return {key: json.loads(value) for key, value in
            connection.execute("SELECT key, value FROM metadata")}


def object_catalog_report(path):
    catalog = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(catalog)) as connection:
        metadata = _read_metadata(connection)
        object_count, cataloged = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(point_count), 0) FROM objects").fetchone()
        identifier_range = connection.execute("SELECT MIN(object_id), MAX(object_id) FROM objects").fetchone()
        largest = connection.execute(
            "SELECT object_id, point_count FROM objects ORDER BY point_count DESC, object_id LIMIT 5").fetchall()
    return {
        "status": "READY",
        "catalog_path": str(catalog),
        "source_sha256": metadata["source_sha256"],
        "field": metadata["field"],
        "field_dtype": metadata["field_dtype"],
        "editable_integer_ids": metadata["field_kind"] in ("i", "u"),
        "source_point_count": metadata["source_point_count"],
        "cataloged_point_count": int(cataloged),
        "missing_value_count": metadata["missing_value_count"],
        "object_count": int(object_count),
        "minimum_object_id": identifier_range[0],
        "maximum_object_id": identifier_range[1],
        "largest_objects": [[int(identifier), int(count)] for identifier, count in largest],
        "exact": True,
        "bounded_memory": True,
        "chunk_size": CHUNK_SIZE,
        "duration_seconds": metadata["duration_seconds"],
        "modifies_source_or_journal": False,
    }


def build_object_catalog(chunks, expected_points, field, destination, source_sha256, *,
                         cancelled=lambda: False, progress=lambda count: None):
    """Atomically build exact counts and bounds using chunk-local aggregation."""
    if type(expected_points) is not int or expected_points < 0:
        raise ValueError("Expected source point count must be a non-negative integer.")
    field = _validated_field(field)
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("Object catalog requires the source content fingerprint.")
    import numpy as np

    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".building-" + uuid4().hex)
    started = monotonic()
    scanned = missing = 0
    field_dtype = None
    connection = None
    try:
        connection = sqlite3.connect(temporary)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("""CREATE TABLE objects (
            object_id INTEGER PRIMARY KEY, point_count INTEGER NOT NULL,
            min_x REAL NOT NULL, min_y REAL NOT NULL, min_z REAL NOT NULL,
            max_x REAL NOT NULL, max_y REAL NOT NULL, max_z REAL NOT NULL)""")
        statement = """INSERT INTO objects VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(object_id) DO UPDATE SET
              point_count=point_count+excluded.point_count,
              min_x=MIN(min_x,excluded.min_x), min_y=MIN(min_y,excluded.min_y),
              min_z=MIN(min_z,excluded.min_z), max_x=MAX(max_x,excluded.max_x),
              max_y=MAX(max_y,excluded.max_y), max_z=MAX(max_z,excluded.max_z)"""
        for chunk in chunks:
            if cancelled():
                raise InterruptedError("Object catalog cancelled; source and journal are unchanged.")
            names = chunk.dtype.names or ()
            if field not in names:
                raise ValueError(f"Source does not contain catalog field {field} and XYZ coordinates.")
            current_dtype = str(chunk.dtype.fields[field][0])
            if field_dtype is None:
                field_dtype = current_dtype
            elif current_dtype != field_dtype:
                raise ValueError("Object catalog field storage type changed during source scan.")
            rows, chunk_missing = _chunk_rows(chunk, field, np)
            with connection:
                connection.executemany(statement, rows)
            scanned += len(chunk)
            missing += chunk_missing
            progress(scanned)
        if scanned != expected_points:
            raise ValueError("Object catalog source count differs from the verified header.")
        if field_dtype is None:
            raise ValueError("Object catalog cannot infer the field storage type from an empty source.")
        duration = monotonic() - started
        metadata = {
            "source_sha256": source_sha256, "field": field, "field_dtype": field_dtype,
            "field_kind": np.dtype(field_dtype).kind,
            "source_point_count": scanned, "missing_value_count": missing,
            "duration_seconds": duration,
        }
        with connection:
            connection.executemany("INSERT INTO metadata VALUES (?, ?)",
                ((key, json.dumps(value, allow_nan=False)) for key, value in metadata.items()))
        connection.close()
        connection = None
        os.replace(temporary, destination)
        return object_catalog_report(destination)
    finally:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)


def build_source_object_catalog(source, expected_points, field, destination, *, pdal_module=None,
                                cancelled=lambda: False, progress=lambda count: None):
    """Build, verify source identity again, then promote over any previous catalog."""
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    destination = Path(destination).resolve()
    verified = destination.with_name(destination.name + ".verified-" + uuid4().hex)
    source.verify(cancelled=cancelled)
    reader = {"type": "readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename": source.path}
    try:
        chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=CHUNK_SIZE, prefetch=0)
        build_object_catalog(chunks, expected_points, field, verified, source.sha256,
                             cancelled=cancelled, progress=progress)
        source.verify(cancelled=cancelled)
        os.replace(verified, destination)
        return object_catalog_report(destination)
    finally:
        verified.unlink(missing_ok=True)


def _validated_catalog(path, source_sha256=None, field=None):
    report = object_catalog_report(path)
    if source_sha256 is not None and report["source_sha256"] != source_sha256:
        raise ValueError("Object catalog belongs to another source.")
    if field is not None and report["field"] != field:
        raise ValueError("Object catalog belongs to another source dimension.")
    return report


def catalog_object(path, object_id, *, source_sha256=None, field=None):
    _validated_catalog(path, source_sha256, field)
    if type(object_id) is not int or not MIN_INT64 <= object_id <= MAX_INT64:
        raise ValueError("Object ID must be a signed 64-bit integer.")
    with closing(sqlite3.connect(Path(path))) as connection:
        row = connection.execute("SELECT * FROM objects WHERE object_id=?", (object_id,)).fetchone()
    if row is None:
        return None
    keys = ("object_id", "point_count", "min_x", "min_y", "min_z", "max_x", "max_y", "max_z")
    return dict(zip(keys, row))


def catalog_neighbor(path, current_id=None, direction=1, *, source_sha256=None, field=None):
    _validated_catalog(path, source_sha256, field)
    if direction not in (-1, 1):
        raise ValueError("Object navigation direction must be previous or next.")
    if current_id is not None and type(current_id) is not int:
        raise ValueError("Current object ID must be an integer.")
    if current_id is None:
        clause, parameters = ("ORDER BY object_id ASC" if direction > 0 else "ORDER BY object_id DESC"), ()
    elif direction > 0:
        clause, parameters = "WHERE object_id>? ORDER BY object_id ASC", (current_id,)
    else:
        clause, parameters = "WHERE object_id<? ORDER BY object_id DESC", (current_id,)
    with closing(sqlite3.connect(Path(path))) as connection:
        row = connection.execute("SELECT object_id FROM objects " + clause + " LIMIT 1", parameters).fetchone()
    return None if row is None else catalog_object(path, int(row[0]),
        source_sha256=source_sha256, field=field)


def object_selection_definition(session, field, row):
    """Describe one catalog object through the shared authoritative selection contract."""
    from .selection import SelectionDefinition

    field = _validated_field(field)
    required = ("object_id", "point_count", "min_x", "min_y", "min_z", "max_x", "max_y", "max_z")
    if not isinstance(row, dict) or any(key not in row for key in required):
        raise ValueError("Object catalog row is incomplete.")
    object_id = row["object_id"]
    if type(object_id) is not int or not MIN_INT64 <= object_id <= MAX_INT64:
        raise ValueError("Object ID must be a signed 64-bit integer.")
    bounds = tuple(row[key] for key in required[2:])
    if (any(type(value) not in (int, float) or not math.isfinite(value) for value in bounds)
            or any(bounds[index] > bounds[index + 3] for index in range(3))):
        raise ValueError("Object catalog row has invalid source bounds.")
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    if xmin == xmax:
        pad = max(1e-9, abs(xmin) * 1e-12)
        xmin, xmax = xmin - pad, xmax + pad
    if ymin == ymax:
        pad = max(1e-9, abs(ymin) * 1e-12)
        ymin, ymax = ymin - pad, ymax + pad
    geometry = ((xmin,ymin), (xmax,ymin), (xmax,ymax), (xmin,ymax), (xmin,ymin))
    return SelectionDefinition(uuid4().hex, session.session_id, session.source.sha256,
        session.source.source_type, geometry, session.source_crs,
        z_filter=(zmin,zmax), attribute_filters=((field,object_id,object_id),),
        depth_mode="CUSTOM_DEPTH_RANGE", view_name=f"Object {field}={object_id}")


def object_catalog_summary(report):
    if not isinstance(report, dict) or report.get("status") != "READY" or not report.get("exact"):
        raise ValueError("Invalid object catalog report.")
    return (f"Object catalog: {report['field']} | {report['object_count']:,} exact objects | "
            f"{report['cataloged_point_count']:,} points")
