"""Explicit bounded-memory materialization through PDAL, never into the source."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from time import monotonic
from uuid import uuid4

from ..atomic_state import atomic_write_json
from .edit_plan import EditExecutionPlan
from .session import SourceIdentity

CHUNK_SIZE = 65_536


def writer_header_options(header):
    """PDAL rejects explicitly empty string options; retain all meaningful fields."""
    fields = ("minor_version", "dataformat_id", "filesource_id", "global_encoding",
              "project_id", "system_id", "creation_doy", "creation_year",
              "scale_x", "scale_y", "scale_z", "offset_x", "offset_y", "offset_z")
    return {key: header[key] for key in fields if header.get(key) is not None and header[key] != ""}


def header_metadata(path):
    import pdal
    probe = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(path), "count": 1}]))
    probe.execute()
    return probe.metadata["metadata"]["readers.las"]


def preserved_vlrs(metadata):
    result = []
    for key, value in metadata.items():
        if not key.startswith("vlr_") or not isinstance(value, dict):
            continue
        user, record = value["user_id"], value["record_id"]
        if user in ("copc", "laszip encoded", "LASF_Projection", "liblas"):
            continue
        if user == "LASF_Spec" and record not in (0, 3):
            continue
        result.append({k: value[k] for k in ("user_id", "record_id", "description", "data")})
    return result


def export_edited(session, destination, *, cancelled=lambda: False, progress=lambda stage, count: None):
    import numpy as np
    import pdal
    from pyproj import CRS

    source = Path(session.source.path).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination == source or (destination.exists() and destination.samefile(source)):
        raise ValueError("Export must never overwrite the original source.")
    if destination.suffix.lower() not in (".las", ".laz") or destination.name.lower().endswith(".copc.laz"):
        raise ValueError("Edited export currently supports LAS/LAZ; COPC export is not qualified.")
    report_path = destination.with_name(destination.name + ".export_validation.json")
    if destination.exists() or report_path.exists():
        raise FileExistsError("Choose a new output filename; existing files are never overwritten.")
    if not destination.parent.is_dir():
        raise ValueError("Choose an existing writable output folder.")
    started = monotonic()
    progress("Verifying original", 0)
    session.source.verify(cancelled=cancelled)
    header = header_metadata(source)
    if header["dataformat_id"] in (4, 5, 9, 10):
        raise ValueError("Waveform point formats are not qualified for edited export.")
    if header["dataformat_id"] < 6 and any(
            (op.value if getattr(op, "attribute", "") == "Classification" else getattr(op, "classification", 0)) > 31
            for op in session.operations):
        raise ValueError("This legacy LAS point format supports classification 0-31; use a qualified format conversion first.")
    plan = EditExecutionPlan(session.operations)
    temporary = destination.parent / ("." + uuid4().hex + ".partial" + destination.suffix)
    temporary_report = destination.parent / ("." + uuid4().hex + ".export-validation.json")
    staging = destination.parent / ("." + uuid4().hex + ".edited-points.partial")
    mapped = writer = readback = output_iterator = None
    changes = {"classification_changed": 0, "noise_assigned": 0, "withheld_set": 0, "withheld_cleared": 0}
    object_fields = sorted({op.attribute for op in session.operations
                            if getattr(op, "kind", "") == "SET_OBJECT_ID"})
    changes["object_id_changed"] = {field: 0 for field in object_fields}

    def chunks(*, track_changes=False):
        pipeline = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(source)}]))
        for original in pipeline.iterator(chunk_size=CHUNK_SIZE, prefetch=0):
            if cancelled():
                raise InterruptedError("Export cancelled; staged edits remain saved.")
            edited, removed = plan.apply(original)
            if track_changes:
                kept = ~removed
                changed = (edited["Classification"] != original["Classification"]) & kept
                changes["classification_changed"] += int(changed.sum())
                changes["noise_assigned"] += int((changed & np.isin(edited["Classification"], (7, 18))).sum())
                if "Withheld" in original.dtype.names:
                    changes["withheld_set"] += int(((original["Withheld"] == 0) & (edited["Withheld"] != 0) & kept).sum())
                    changes["withheld_cleared"] += int(((original["Withheld"] != 0) & (edited["Withheld"] == 0) & kept).sum())
                for field in object_fields:
                    changes["object_id_changed"][field] += int(
                        ((edited[field] != original[field]) & kept).sum())
            yield edited[~removed], len(original), int(removed.sum())

    total = removed_count = written = 0
    try:
        iterator = iter(chunks(track_changes=True))
        first, first_read, first_removed = next(iterator)
        dtype = first.dtype
        required_space = header["count"] * dtype.itemsize + source.stat().st_size * 2
        if shutil.disk_usage(destination.parent).free < required_space:
            raise ValueError("Insufficient temporary disk space for safe disk-backed export.")
        mapped = np.memmap(staging, dtype=dtype, mode="w+", shape=(max(1, header["count"]),))
        import itertools
        for values, read_count, dropped in itertools.chain(((first, first_read, first_removed),), iterator):
            if cancelled():
                raise InterruptedError("Export cancelled; staged edits remain saved.")
            mapped[written:written + len(values)] = values
            total += read_count
            removed_count += dropped
            written += len(values)
            progress("Staging edits on disk", total)
        mapped.flush()

        options = writer_header_options(header)
        options.update(type="writers.las", filename=str(temporary),
                       compression=destination.suffix.lower() == ".laz", extra_dims="all",
                       vlrs=preserved_vlrs(header))
        wkt = header.get("comp_spatialreference") or header.get("spatialreference") or ""
        if wkt:
            options["a_srs"] = wkt
        progress("Writing edited cloud", written)
        writer = pdal.Pipeline(json.dumps([options]), arrays=[mapped[:written]])
        writer.execute_streaming(CHUNK_SIZE)
        writer = None
        if total != header["count"]:
            raise ValueError("Source read count changed during export.")
        progress("Validating every output dimension", 0)
        readback = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(temporary)}]))
        output_iterator = iter(readback.iterator(chunk_size=CHUNK_SIZE, prefetch=0))
        actual = None
        offset = validated = 0
        counts = {}
        for expected, _read, _removed in chunks():
            start = 0
            while start < len(expected):
                if actual is None or offset == len(actual):
                    actual = next(output_iterator, None)
                    offset = 0
                    if actual is None:
                        raise ValueError("Export is missing expected source points.")
                names = expected.dtype.names
                if not set(names) <= set(actual.dtype.names):
                    raise ValueError("Export lost source dimensions.")
                length = min(len(expected) - start, len(actual) - offset)
                for name in names:
                    if not np.array_equal(expected[name][start:start+length], actual[name][offset:offset+length], equal_nan=True):
                        raise ValueError(f"Export validation failed for {name}; original/session remain unchanged.")
                codes, amounts = np.unique(actual["Classification"][offset:offset+length], return_counts=True)
                for code, amount in zip(codes, amounts):
                    counts[int(code)] = counts.get(int(code), 0) + int(amount)
                start += length
                offset += length
                validated += length
            progress("Validating every output dimension", validated)
        if (actual is not None and offset < len(actual)) or next(output_iterator, None) is not None or validated != written:
            raise ValueError("Export contains unexpected points.")
        output_header = header_metadata(temporary)
        out_wkt = output_header.get("comp_spatialreference") or output_header.get("spatialreference") or ""
        if bool(wkt) != bool(out_wkt) or (wkt and not CRS.from_user_input(wkt).equals(CRS.from_user_input(out_wkt))):
            raise ValueError("Export changed the source CRS.")
        required_vlrs = {(v["user_id"], v["record_id"], v["data"]) for v in preserved_vlrs(header)}
        actual_vlrs = {(v["user_id"], v["record_id"], v["data"]) for v in preserved_vlrs(output_header)}
        if not required_vlrs <= actual_vlrs:
            raise ValueError("Export lost preserved VLR payloads.")
        session.source.verify(cancelled=cancelled)
        identity = SourceIdentity.capture(temporary, cancelled=cancelled)
        report = {"status": "VALIDATED", "export_id": uuid4().hex, "session_id": session.session_id,
                  "attribute_changes": changes, "source_points_modified": 0,
                  "original_source": str(source), "original_sha256": session.source.sha256,
                  "output": str(destination), "output_sha256": identity.sha256,
                  "original_unchanged": True, "point_count": written, "source_point_count": total,
                  "removed_point_count": removed_count, "classification_counts": counts,
                  "dimensions": list(dtype.names), "all_dimension_values_match_journal": True,
                  "crs_preserved": True, "custom_vlr_payloads_preserved": True,
                  "format_metadata_note": "PDAL regenerates compression, CRS and Extra Bytes layout records.",
                  "header_normalizations": {key: {"source": header.get(key), "output": output_header.get(key)}
                      for key in ("system_id", "project_id") if header.get(key) != output_header.get(key)},
                  "staging_policy": "DISK_BACKED_NUMPY_EXISTING_PDAL", "staging_bytes": staging.stat().st_size,
                  "staged_operations": len(session.operations), "duration_seconds": monotonic() - started}
        atomic_write_json(temporary_report, report)
        if cancelled():
            raise InterruptedError("Export cancelled before publication.")
        # Atomic no-clobber publication; unsupported filesystems fail safely.
        os.link(temporary_report, report_path)
        try:
            os.link(temporary, destination)
        except BaseException:
            report_path.unlink()
            raise
        progress("Export complete", written)
        return report
    finally:
        writer = readback = output_iterator = None
        if mapped is not None:
            mapped._mmap.close()
        for path in (temporary, temporary_report, staging):
            if path.exists():
                path.unlink()
