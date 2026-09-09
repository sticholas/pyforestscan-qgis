"""Source-space selection contracts. Scientific imports occur only in workers.

Selection membership uses ORIGINAL attributes and inclusive polygon boundaries.
A rendered sample, preview count, or camera point index is never an address.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import math
import re
from time import monotonic

from .session import SourceIdentity


def _range(value, label):
    if value is None:
        return None
    result = tuple(value)
    if (len(result) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in result)
            or result[0] > result[1]):
        raise ValueError(f"Invalid {label} range.")
    return result


@dataclass(frozen=True)
class SelectionDefinition:
    selection_id: str
    session_id: str
    source_fingerprint: str
    source_type: str
    geometry: tuple[tuple[float, float], ...]
    geometry_crs: str
    selection_mode: str = "REPLACE"
    z_filter: tuple[float, float] | None = None
    hag_filter: tuple[float, float] | None = None
    classification_filter: tuple[int, ...] | None = None
    attribute_filters: tuple[tuple[str, float, float], ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    addressing: str = "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY"

    def __post_init__(self):
        if not self.selection_id or not self.session_id or not self.geometry_crs.strip():
            raise ValueError("Selection, session and source CRS identities are required.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_fingerprint):
            raise ValueError("Selection requires an original source fingerprint.")
        if self.source_type not in ("LAS", "LAZ", "COPC"):
            raise ValueError("EPT editing requires immutable affected-node identity; not enabled.")
        if self.addressing != "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY":
            raise ValueError("Rendered LOD indices are not authoritative selection addresses.")
        if self.selection_mode not in ("REPLACE", "ADD", "SUBTRACT"):
            raise ValueError("Unsupported selection mode.")
        ring = tuple(tuple(point) for point in self.geometry)
        if not 4 <= len(ring) <= 4097 or ring[0] != ring[-1]:
            raise ValueError("Selection polygon must be closed with 3-4096 vertices.")
        if any(len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in ring):
            raise ValueError("Selection requires finite source XY coordinates.")
        object.__setattr__(self, "geometry", ring)
        object.__setattr__(self, "z_filter", _range(self.z_filter, "Z"))
        object.__setattr__(self, "hag_filter", _range(self.hag_filter, "HAG"))
        if self.classification_filter is not None:
            classes = tuple(self.classification_filter)
            if any(type(c) is not int or not 0 <= c <= 255 for c in classes):
                raise ValueError("Invalid classification filter.")
            object.__setattr__(self, "classification_filter", classes)
        filters = tuple(tuple(item) for item in self.attribute_filters)
        for item in filters:
            if len(item) != 3 or not isinstance(item[0], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", item[0]):
                raise ValueError("Invalid attribute filter.")
            if item[0] in ("X", "Y", "Z", "Classification", "HeightAboveGround"):
                raise ValueError("Use the explicit geometry/class/height filter.")
            _range(item[1:], item[0])
        object.__setattr__(self, "attribute_filters", filters)


@dataclass(frozen=True)
class SelectionResult:
    selection_id: str
    resolution_status: str
    resolved_point_count: int
    bounds: tuple[float, ...] | None
    classification_counts: tuple[tuple[int, int], ...]
    z_min: float | None
    z_max: float | None
    hag_min: float | None
    hag_max: float | None
    source_partitions: tuple[str, ...]
    resolution_seconds: float
    candidate_point_count: int


def validate_sequence(definitions):
    items = tuple(definitions)
    if not items or len(items) > 1024 or items[0].selection_mode != "REPLACE":
        raise ValueError("A bounded selection sequence must begin with Replace.")
    first = items[0]
    key = (first.session_id, first.source_fingerprint, first.source_type, first.geometry_crs)
    ids = set()
    for item in items:
        if (item.session_id, item.source_fingerprint, item.source_type, item.geometry_crs) != key:
            raise ValueError("Selection sequence mixes sources, sessions or CRSs.")
        if item.selection_id in ids:
            raise ValueError("Duplicate selection identity.")
        ids.add(item.selection_id)
    # Earlier state has no effect after the most recent Replace.
    start = max(i for i, item in enumerate(items) if item.selection_mode == "REPLACE")
    return items[start:]


def reader_spec(source, definitions):
    items = validate_sequence(definitions)
    if (source.sha256, source.source_type) != (items[0].source_fingerprint, items[0].source_type):
        raise ValueError("Selection does not belong to this original source.")
    reader = {"type": "readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename": source.path}
    if source.source_type == "COPC":
        points = [p for item in items if item.selection_mode != "SUBTRACT" for p in item.geometry]
        xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
        ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
        reader["bounds"] = f"([{xmin},{xmax}],[{ymin},{ymax}])"
        reader["threads"] = 2
        # No resolution/depth/point-budget option: all intersecting source levels.
    return reader


def reader_specs(source, definitions):
    """Separate positive regions avoid reading the empty space between lassos."""
    items = validate_sequence(definitions)
    if source.source_type != "COPC":
        return (reader_spec(source, items),)
    return tuple(reader_spec(source, (replace(item, selection_mode="REPLACE"),))
                 for item in items if item.selection_mode != "SUBTRACT")


def _candidate_chunks(source, items, pdal, np):
    import json
    previous = []
    positive = [item for item in items if item.selection_mode != "SUBTRACT"]
    for index, spec in enumerate(reader_specs(source, items)):
        pipeline = pdal.Pipeline(json.dumps([spec]))
        for chunk in pipeline.iterator(chunk_size=65_536, prefetch=0):
            # A source point belongs to the first query envelope containing it.
            # This preserves coincident original records while avoiding repeated
            # reads of overlapping regions becoming repeated selection members.
            if previous:
                keep = np.ones(len(chunk), dtype=bool)
                for xmin, ymin, xmax, ymax in previous:
                    keep &= ~((chunk["X"] >= xmin) & (chunk["X"] <= xmax) &
                              (chunk["Y"] >= ymin) & (chunk["Y"] <= ymax))
                chunk = chunk[keep]
            yield chunk
        if source.source_type == "COPC":
            ring = positive[index].geometry
            previous.append((min(p[0] for p in ring), min(p[1] for p in ring),
                             max(p[0] for p in ring), max(p[1] for p in ring)))


def selection_mask(chunk, definitions, shapes=None):
    """Shared original-attribute membership for resolution and journal replay."""
    import numpy as np
    import shapely
    items = validate_sequence(definitions)
    shapes = shapes if shapes is not None else [shapely.Polygon(item.geometry) for item in items]
    if any(not shape.is_valid or shape.is_empty or shape.area <= 0 for shape in shapes):
        raise ValueError("Selection polygon is empty or invalid; redraw it.")
    names = set(chunk.dtype.names or ())
    selected = np.zeros(len(chunk), dtype=bool)
    for item, shape in zip(items, shapes):
        mask = shapely.intersects_xy(shape, chunk["X"], chunk["Y"])
        for dimension, limits in (("Z", item.z_filter), ("HeightAboveGround", item.hag_filter)):
            if limits is not None:
                if dimension not in names:
                    raise ValueError(f"Source does not contain {dimension}.")
                mask &= (chunk[dimension] >= limits[0]) & (chunk[dimension] <= limits[1])
        if item.classification_filter is not None:
            mask &= np.isin(chunk["Classification"], item.classification_filter)
        for dimension, low, high in item.attribute_filters:
            if dimension not in names:
                raise ValueError(f"Source does not contain {dimension}.")
            mask &= (chunk[dimension] >= low) & (chunk[dimension] <= high)
        if item.selection_mode == "REPLACE":
            selected = mask
        elif item.selection_mode == "ADD":
            selected |= mask
        else:
            selected &= ~mask
    return selected


class SelectionResolver:
    """Worker-only resolver; retain one instance per verified source session.

    Hash once on attachment, then reject file-stat changes before/after queries.
    Export/reopen must independently verify the full content fingerprint again.
    This is not a cryptographic guarantee against hostile same-stat mutation.
    """

    def __init__(self, source: SourceIdentity, *, cancelled=lambda: False):
        from pathlib import Path
        self.source = source
        self.path = Path(source.path)
        before = self._stamp()
        source.verify(cancelled=cancelled)
        self.stamp = self._stamp()
        if before != self.stamp:
            raise ValueError("Source changed during selection attachment.")

    def _stamp(self):
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def _check_source(self):
        if self._stamp() != self.stamp:
            raise ValueError("Source changed; reopen and verify before selecting.")

    def resolve(self, definitions, *, cancelled=lambda: False, progress=lambda count: None):
        import json
        import numpy as np
        import pdal
        import shapely
        from pyproj import CRS

        started = monotonic()
        items = validate_sequence(definitions)
        self._check_source()
        reader = reader_specs(self.source, items)[0]
        shapes = [shapely.Polygon(item.geometry) for item in items]
        if any(not shape.is_valid or shape.is_empty or shape.area <= 0 for shape in shapes):
            raise ValueError("Selection polygon is empty or invalid; redraw it.")
        for shape in shapes:
            shapely.prepare(shape)
        pipeline = pdal.Pipeline(json.dumps([reader]))
        metadata = next(iter(pipeline.quickinfo.values()))
        dimensions = metadata.get("dimensions", "")
        names = set(d.strip() for d in dimensions.split(",")) if isinstance(dimensions, str) else set(dimensions)
        required = {"X", "Y", "Z", "Classification"}
        for item in items:
            if item.hag_filter is not None:
                required.add("HeightAboveGround")
            required.update(d for d, _low, _high in item.attribute_filters)
        if required - names:
            raise ValueError("Source does not contain " + ", ".join(sorted(required - names)) + ".")
        if int(metadata.get("num_points", 0)) <= 0:
            raise ValueError("Original source has no verified point count.")
        # Raw inputs are scanned in bounded chunks by the isolated editor worker.
        # Never substitute reordered view-cache records as selection authority.
        srs = metadata.get("srs", {})
        wkt = srs.get("compoundwkt") or srs.get("wkt") or ""
        requested = items[0].geometry_crs
        if wkt:
            if not CRS.from_user_input(wkt).equals(CRS.from_user_input(requested)):
                raise ValueError("Selection geometry is not in the original source CRS.")
        elif requested != "SOURCE_LOCAL:" + self.source.sha256:
            raise ValueError("Source CRS is unknown; an explicit source-local identity is required.")

        count = candidates = 0
        bounds = None
        counts = {}
        hag_min = hag_max = None
        for chunk in _candidate_chunks(self.source, items, pdal, np):
            if cancelled():
                raise InterruptedError("Selection cancelled; no edits staged.")
            self._check_source()
            names = set(chunk.dtype.names or ())
            if not {"X", "Y", "Z", "Classification"} <= names:
                raise ValueError("Source lacks required XYZ/classification dimensions.")
            selected = selection_mask(chunk, items, shapes)
            candidates += len(chunk)
            matched = chunk[selected]
            count += len(matched)
            if len(matched):
                xyz = tuple(float(matched[d].min()) for d in ("X", "Y", "Z")) + tuple(float(matched[d].max()) for d in ("X", "Y", "Z"))
                if not all(math.isfinite(v) for v in xyz):
                    raise ValueError("Selected source coordinates are not finite.")
                bounds = xyz if bounds is None else tuple(min(bounds[i], xyz[i]) if i < 3 else max(bounds[i], xyz[i]) for i in range(6))
                classes, numbers = np.unique(matched["Classification"], return_counts=True)
                for code, number in zip(classes, numbers):
                    counts[int(code)] = counts.get(int(code), 0) + int(number)
                if "HeightAboveGround" in names:
                    values = matched["HeightAboveGround"]
                    values = values[np.isfinite(values)]
                    if len(values):
                        low, high = float(values.min()), float(values.max())
                        hag_min = low if hag_min is None else min(hag_min, low)
                        hag_max = high if hag_max is None else max(hag_max, high)
            progress(count)
        if cancelled():
            raise InterruptedError("Selection cancelled; no edits staged.")
        self._check_source()
        return SelectionResult(items[-1].selection_id, "RESOLVED", count, bounds,
                               tuple(sorted(counts.items())), bounds[2] if bounds else None,
                               bounds[5] if bounds else None, hag_min, hag_max,
                               (self.source.path,) if count else (), monotonic() - started, candidates)
