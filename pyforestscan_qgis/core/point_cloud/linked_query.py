"""Read-only, bounded-memory display extraction from original source records."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time

from .workspace import AreaGeometry, SliceGeometry


@dataclass(frozen=True)
class EPTViewIdentity:
    """Metadata identity for read-only queries, NEVER an editing fingerprint."""
    path: str
    sha256: str
    source_type: str = "EPT"

    def verify(self, *, cancelled=lambda: False):
        if cancelled():
            raise InterruptedError("EPT metadata verification cancelled.")
        with Path(self.path).open("rb") as stream:
            raw = stream.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024 or hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError("EPT metadata changed; reopen the source.")


def area_ring(geometry):
    import math
    area = AreaGeometry(**geometry)
    if area.shape == "POLYGON":
        return area.vertices
    x, y = area.center
    if area.shape == "CIRCLE":
        ring = tuple((x+area.radius*math.cos(i*math.tau/128),
                      y+area.radius*math.sin(i*math.tau/128)) for i in range(128))
        return (*ring, ring[0])
    dx, dy = area.width/2, area.height/2
    return ((x-dx,y-dy),(x+dx,y-dy),(x+dx,y+dy),(x-dx,y+dy),(x-dx,y-dy))


def _distribution(counts, total):
    return [{"value": key, "count": int(value),
             "percentage": (100.0 * value / total) if total else 0.0}
            for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _profile_statistics(values, count, minimum, maximum, total, np):
    from .profile_statistics import finalize_numeric_statistics
    result = finalize_numeric_statistics(values, count=count, minimum=minimum,
                                         maximum=maximum, total=total, np=np)
    result["axis"] = "profile_vertical"
    return result


def view_ring(view):
    if view["view_type"] == "AREA_DETAIL":
        return area_ring(view["geometry"])
    if view["view_type"] == "VERTICAL_SLICE":
        return SliceGeometry(**view["geometry"]).corridor()
    raise ValueError("Only bounded detail/profile views can be extracted.")


def extract_view(source, view, output_dir, *, index_root, point_budget,
                 cancelled=lambda: False, progress=lambda stage,count: None, display_path=None):
    import numpy as np
    import pdal
    import shapely
    from pyproj import CRS
    from .source_index import RawSpatialIndex

    started = time.monotonic()
    if type(point_budget) is not int or point_budget <= 0:
        raise ValueError("A positive coordinated display budget is required.")
    profile = SliceGeometry(**view["geometry"]) if view["view_type"]=="VERTICAL_SLICE" else None
    if profile:
        from .profile import profile_corridor_shape, profile_query_envelopes
        polygon = profile_corridor_shape(profile, shapely)
    else:
        polygon = shapely.Polygon(view_ring(view))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("The view boundary is empty or self-intersecting.")
    xmin, ymin, xmax, ymax = polygon.bounds
    kind = "COPC" if display_path is not None else source.source_type
    reader = {"type":{"COPC":"readers.copc","EPT":"readers.ept","LAS":"readers.las","LAZ":"readers.las"}[kind],
              "filename":str(display_path) if display_path is not None else source.path}
    metadata = next(iter(pdal.Pipeline(json.dumps([reader])).quickinfo.values()))
    srs = metadata.get("srs", {})
    wkt = srs.get("compoundwkt") or srs.get("wkt") or ""
    requested_crs = view["geometry"]["crs"]
    if wkt and not CRS.from_user_input(wkt).equals(CRS.from_user_input(requested_crs)):
        raise ValueError("View geometry is not in original source coordinates.")
    if not wkt and requested_crs != "SOURCE_LOCAL:" + source.sha256:
        raise ValueError("Unknown source CRS requires its source-local identity.")
    if kind in ("LAS", "LAZ"):
        index = RawSpatialIndex(source, index_root)
        index.ensure(cancelled=cancelled, progress=lambda count:progress("Indexing original record ranges",count))
        envelopes = profile_query_envelopes(profile) if profile else ((xmin,ymin,xmax,ymax),)
        chunks = index.chunks(envelopes, cancelled=cancelled)
    else:
        reader.update(bounds=f"([{xmin},{xmax}],[{ymin},{ymax}])", threads=2)
        if profile:
            reader["polygon"] = polygon.wkt
        chunks = pdal.Pipeline(json.dumps([reader])).iterator(chunk_size=65536,prefetch=0)
    seed = int(hashlib.sha256(json.dumps([source.sha256,view["geometry"]],sort_keys=True).encode()).hexdigest()[:16],16)
    random = np.random.default_rng(seed)
    sample = keys = None
    count = candidates = 0
    class_counts = {}
    value_count = 0
    value_min = value_max = value_sum = None
    value_sample = np.empty(0, dtype="f8")
    return_counts = {}
    number_return_counts = {}
    intensity_count = 0
    intensity_min = intensity_max = intensity_sum = None
    for chunk in chunks:
        if cancelled():
            raise InterruptedError("Linked view query cancelled.")
        candidates += len(chunk)
        mask = shapely.intersects_xy(polygon, chunk["X"], chunk["Y"])
        if profile:
            if profile.vertical_axis not in chunk.dtype.names:
                raise ValueError(f"Source does not contain {profile.vertical_axis}.")
            mask &= np.isfinite(chunk[profile.vertical_axis])
            if profile.vertical_limits is not None:
                low, high = profile.vertical_limits
                mask &= (chunk[profile.vertical_axis] >= low) & (chunk[profile.vertical_axis] <= high)
        selected = chunk[mask]
        count += len(selected)
        if profile and len(selected):
            values = selected[profile.vertical_axis]
            value_count += len(values)
            chunk_min, chunk_max = float(np.min(values)), float(np.max(values))
            value_min = chunk_min if value_min is None else min(value_min, chunk_min)
            value_max = chunk_max if value_max is None else max(value_max, chunk_max)
            chunk_sum = float(np.sum(values, dtype="f8"))
            value_sum = chunk_sum if value_sum is None else value_sum + chunk_sum
            value_sample = np.concatenate((value_sample, values.astype("f8", copy=False)))
            if len(value_sample) > 100000:
                value_sample = value_sample[:100000]
            for field, target in (("ReturnNumber", return_counts), ("NumberOfReturns", number_return_counts)):
                if field in selected.dtype.names:
                    codes, totals = np.unique(selected[field], return_counts=True)
                    for code, total in zip(codes, totals):
                        target[int(code)] = target.get(int(code), 0) + int(total)
            if "Intensity" in selected.dtype.names:
                intensity = selected["Intensity"].astype("f8", copy=False)
                intensity_count += len(intensity)
                chunk_min, chunk_max = float(np.min(intensity)), float(np.max(intensity))
                intensity_min = chunk_min if intensity_min is None else min(intensity_min, chunk_min)
                intensity_max = chunk_max if intensity_max is None else max(intensity_max, chunk_max)
                chunk_sum = float(np.sum(intensity, dtype="f8"))
                intensity_sum = chunk_sum if intensity_sum is None else intensity_sum + chunk_sum
        if len(selected):
            if profile and "Classification" in selected.dtype.names:
                classes, totals = np.unique(selected["Classification"], return_counts=True)
                for code, total in zip(classes, totals):
                    key = int(code)
                    class_counts[key] = class_counts.get(key, 0) + int(total)
            new_keys = random.random(len(selected))
            sample = selected if sample is None else np.concatenate((sample,selected))
            keys = new_keys if keys is None else np.concatenate((keys,new_keys))
            if len(sample) > point_budget:
                keep = np.argpartition(keys,point_budget-1)[:point_budget]
                sample, keys = sample[keep], keys[keep]
        progress("Reading bounded original points",count)
    if cancelled():
        raise InterruptedError("Linked view query cancelled.")
    if sample is None or not len(sample):
        raise ValueError("No source points fall inside this view.")
    if profile and profile.display_projection == "PROFILE_DISTANCE":
        reserved = {"PFSOriginalX", "PFSOriginalY", "PFSOriginalZ"}
        if reserved & set(sample.dtype.names):
            raise ValueError("Reserved viewer source-coordinate dimensions already exist in the source.")
        from .profile import profile_coordinates
        along, cross, _distance = profile_coordinates(profile, sample["X"], sample["Y"], np)
        vertical = sample[profile.vertical_axis].copy()
        converted = np.empty(len(sample),dtype=sample.dtype.descr+
            [("PFSOriginalX","<f8"),("PFSOriginalY","<f8"),("PFSOriginalZ","<f8")])
        for name in sample.dtype.names:
            converted[name]=sample[name]
        converted["PFSOriginalX"],converted["PFSOriginalY"],converted["PFSOriginalZ"] = (
            sample["X"],sample["Y"],sample["Z"])
        converted["X"],converted["Y"],converted["Z"] = along,cross,vertical
        sample=converted
    elif profile and profile.vertical_axis == "HeightAboveGround":
        if "PFSOriginalZ" in sample.dtype.names:
            raise ValueError("Reserved viewer dimension PFSOriginalZ already exists in the source.")
        converted = np.empty(len(sample),dtype=sample.dtype.descr+[("PFSOriginalZ","<f8")])
        for name in sample.dtype.names:
            converted[name]=sample[name]
        converted["PFSOriginalZ"]=sample["Z"]
        converted["Z"]=sample["HeightAboveGround"]
        sample=converted
    folder = Path(output_dir)
    folder.mkdir(parents=True,exist_ok=False)
    output = folder/"view.laz"
    temporary = folder/"view.partial.laz"
    writer = {"type":"writers.las","filename":str(temporary),"minor_version":4,
              "dataformat_id":7 if "Red" in sample.dtype.names else 6,
              "extra_dims":"all","compression":True,
              "scale_x":"auto","scale_y":"auto","scale_z":"auto",
              "offset_x":"auto","offset_y":"auto","offset_z":"auto"}
    if wkt and not (profile and profile.display_projection == "PROFILE_DISTANCE"):
        writer["a_srs"]=wkt
    progress("Preparing display cache",len(sample))
    try:
        pdal.Pipeline(json.dumps([writer]),arrays=[sample]).execute()
        if cancelled():
            raise InterruptedError("Linked view query cancelled.")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
        if not output.exists():
            folder.rmdir()
    return {"path":str(output),"view_id":view["view_id"],"source_fingerprint":source.sha256,
            "source_points":count,"display_points":len(sample),"candidate_points":candidates,
            "classification_counts":sorted(class_counts.items(), key=lambda item:(-item[1],item[0])),
            "vertical_stats": _profile_statistics(value_sample, value_count, value_min,
                                                   value_max, value_sum, np)
                               if profile and value_count else None,
            "returns": _distribution(return_counts, count),
            "number_of_returns": _distribution(number_return_counts, count),
            "intensity_stats": ({"count": intensity_count, "minimum": intensity_min,
                                 "maximum": intensity_max, "mean": intensity_sum / intensity_count}
                                if intensity_count else None),
            "point_budget":point_budget,"query_seconds":time.monotonic()-started,
            "geometry":view["geometry"],"view_type":view["view_type"],
            "display_projection":profile.display_projection if profile else "SOURCE_XY",
            "identity_scope":"EPT_METADATA_ONLY" if kind=="EPT" else "FULL_ORIGINAL_FILE",
            "display_query_source":"VERIFIED_VIEW_CACHE" if display_path is not None else "ORIGINAL_SOURCE",
            "authority":"ORIGINAL_SOURCE_RECORDS; output is display-only"}
