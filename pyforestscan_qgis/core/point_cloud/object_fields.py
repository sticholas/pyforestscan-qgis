"""Bounded discovery of source dimensions that may identify objects or segments."""
from __future__ import annotations

import json
import math
import re
from time import monotonic


CHUNK_SIZE = 65_536
SAMPLE_POINTS_PER_FIELD = 65_536
MIN_SAMPLE_POINTS_PER_FIELD = 1_024
MAX_TOTAL_SAMPLE_VALUES = 1_048_576
MAX_NONSTANDARD_FIELDS = 256
VALUE_PREVIEW_LIMIT = 12

# LAS dimensions describe measurements or transport metadata, not user object IDs.
_STANDARD_DIMENSIONS = frozenset({
    "x", "y", "z", "intensity", "returnnumber", "numberofreturns",
    "scandirectionflag", "edgeofflightline", "classification", "scananglerank",
    "scanangle", "userdata", "pointsourceid", "gpstime", "red", "green", "blue",
    "infrared", "scanchannel", "classflags", "synthetic", "keypoint", "withheld",
    "overlap", "originid", "pfsoriginalz",
})

_ROLE_TOKENS = (
    ("TREE", ("tree", "crown", "stem")),
    ("SEGMENT", ("segment", "segmentation")),
    ("OBJECT", ("object", "feature")),
    ("INSTANCE", ("instance", "prediction", "predinstance")),
    ("CLUSTER", ("cluster", "group")),
)


def normalized_dimension_name(name):
    """Return a comparison-only dimension name without defining a required schema."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Dimension names must be non-empty text.")
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def semantic_object_role(name):
    """Return a ranking hint; statistical discovery remains available for any name."""
    normalized = normalized_dimension_name(name)
    for role, tokens in _ROLE_TOKENS:
        if any(token in normalized for token in tokens):
            return role
    return "CATEGORICAL"


def _candidate_report(name, tracker):
    sample = tracker["sample"]
    role = semantic_object_role(name)
    integer_values = tracker["integer_values"]
    unique = sorted(set(sample))
    sample_count = len(sample)
    ratio = len(unique) / sample_count if sample_count else 1.0
    semantic = role != "CATEGORICAL"
    candidate = bool(integer_values and sample_count and (
        semantic or (len(unique) >= 2 and ratio <= 0.25)))
    if not integer_values:
        reason = "Values are not integer-like categorical identifiers."
    elif semantic:
        reason = f"Dimension name suggests a {role.lower()} identifier; values are integer-like."
    elif candidate:
        reason = "Repeated integer-like values make this a schema-independent categorical candidate."
    elif len(unique) <= 1:
        reason = "Only one sampled value was observed and the name has no object/segment signal."
    else:
        reason = "Sampled values are too nearly unique to infer a categorical object field safely."
    confidence = "HIGH" if semantic and candidate else "MEDIUM" if candidate else "LOW"
    return {
        "name": name,
        "role": role,
        "candidate": candidate,
        "confidence": confidence,
        "dtype": tracker["dtype"],
        "integer_values": integer_values,
        "populated_point_count": tracker["populated"],
        "sampled_point_count": sample_count,
        "sample_unique_count": len(unique),
        "sample_unique_ratio": ratio,
        "minimum": tracker["minimum"],
        "maximum": tracker["maximum"],
        "zero_count": tracker["zero_count"],
        "negative_count": tracker["negative_count"],
        "value_preview": unique[:VALUE_PREVIEW_LIMIT],
        "reason": reason,
    }


def discover_object_fields(chunks, expected_points, *, cancelled=lambda: False,
                           progress=lambda count: None):
    """Inspect every source point with fixed chunks and bounded per-field samples."""
    if type(expected_points) is not int or expected_points < 0:
        raise ValueError("Expected source point count must be a non-negative integer.")
    import numpy as np

    started = monotonic()
    trackers = None
    source_dimensions = ()
    sample_limit = SAMPLE_POINTS_PER_FIELD
    sample_stride = 1
    scanned = 0
    for chunk in chunks:
        if cancelled():
            raise InterruptedError("Object-field discovery cancelled; source and journal are unchanged.")
        names = tuple(chunk.dtype.names or ())
        if not names:
            raise ValueError("Source chunks must expose named point dimensions.")
        if trackers is None:
            source_dimensions = names
            trackers = {}
            for name in names:
                if normalized_dimension_name(name) in _STANDARD_DIMENSIONS:
                    continue
                dtype = chunk.dtype.fields[name][0]
                trackers[name] = {
                    "dtype": str(dtype), "kind": dtype.kind, "sample": [],
                    "integer_values": dtype.kind in "biu", "populated": 0,
                    "minimum": None, "maximum": None, "zero_count": 0,
                    "negative_count": 0,
                }
            if len(trackers) > MAX_NONSTANDARD_FIELDS:
                raise ValueError(
                    f"Source has more than {MAX_NONSTANDARD_FIELDS} nonstandard dimensions; "
                    "bounded object-field discovery cannot inspect them in one pass.")
            if trackers:
                sample_limit = min(SAMPLE_POINTS_PER_FIELD,
                    max(MIN_SAMPLE_POINTS_PER_FIELD, MAX_TOTAL_SAMPLE_VALUES // len(trackers)))
                sample_stride = max(1, math.ceil(expected_points / sample_limit))
        elif names != source_dimensions:
            raise ValueError("Point dimensions changed during object-field discovery.")

        sample_indices = np.arange((-scanned) % sample_stride, len(chunk), sample_stride)
        for name, tracker in trackers.items():
            values = np.asarray(chunk[name]).reshape(-1)
            if tracker["kind"] in "f":
                finite = values[np.isfinite(values)]
            elif tracker["kind"] in "biu":
                finite = values
            else:
                tracker["integer_values"] = False
                continue
            if not len(finite):
                continue
            tracker["populated"] += int(len(finite))
            low, high = float(finite.min()), float(finite.max())
            tracker["minimum"] = low if tracker["minimum"] is None else min(tracker["minimum"], low)
            tracker["maximum"] = high if tracker["maximum"] is None else max(tracker["maximum"], high)
            tracker["zero_count"] += int((finite == 0).sum())
            tracker["negative_count"] += int((finite < 0).sum())
            if tracker["kind"] == "f" and not np.allclose(finite, np.rint(finite), rtol=0, atol=1e-7):
                tracker["integer_values"] = False
            remaining = sample_limit - len(tracker["sample"])
            if remaining > 0:
                sampled = values[sample_indices]
                if tracker["kind"] == "f":
                    sampled = sampled[np.isfinite(sampled)]
                tracker["sample"].extend(sampled[:remaining].tolist())
        scanned += len(chunk)
        progress(scanned)

    if scanned != expected_points:
        raise ValueError("Object-field discovery source count differs from the verified header.")
    trackers = trackers or {}
    fields = [_candidate_report(name, tracker) for name, tracker in trackers.items()]
    fields.sort(key=lambda item: (not item["candidate"], item["confidence"] != "HIGH",
                                  item["name"].casefold()))
    candidates = [item for item in fields if item["candidate"]]
    return {
        "status": "FOUND" if candidates else "NONE_FOUND",
        "addressing": "FULL_RESOLUTION_ORIGINAL_SOURCE_SEQUENTIAL_DISCOVERY",
        "bounded_memory": True,
        "chunk_size": CHUNK_SIZE,
        "sample_points_per_field": sample_limit,
        "sampling_strategy": "EVENLY_SPACED_SOURCE_ORDER",
        "source_point_count": scanned,
        "source_dimensions": list(source_dimensions),
        "nonstandard_numeric_fields": fields,
        "candidate_fields": candidates,
        "duration_seconds": monotonic() - started,
        "modifies_source_or_journal": False,
    }


def discover_source_object_fields(source, expected_points, *, pdal_module=None,
                                  cancelled=lambda: False, progress=lambda count: None):
    """Verify and stream one local LAS/LAZ/COPC source without materializing it."""
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    source.verify(cancelled=cancelled)
    reader = {"type": "readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename": source.path}
    chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=CHUNK_SIZE, prefetch=0)
    report = discover_object_fields(chunks, expected_points, cancelled=cancelled, progress=progress)
    source.verify(cancelled=cancelled)
    return report


def object_field_discovery_summary(report):
    if not isinstance(report, dict) or report.get("status") not in ("FOUND", "NONE_FOUND"):
        raise ValueError("Invalid object-field discovery report.")
    count = len(report["candidate_fields"])
    if count:
        names = ", ".join(item["name"] for item in report["candidate_fields"][:3])
        suffix = "" if count <= 3 else f" and {count - 3} more"
        return f"Object fields: {count} candidate{'s' if count != 1 else ''} | {names}{suffix}"
    return "Object fields: No categorical object or segment candidates found"
