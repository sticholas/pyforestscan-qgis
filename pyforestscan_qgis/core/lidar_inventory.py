"""LiDAR folder discovery and inventory models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .spatial_selection import Bounds2D

SUPPORTED_LIDAR_SUFFIXES = (".las", ".laz", ".copc", ".copc.laz")


@dataclass(frozen=True)
class LidarFolderRequest:
    """Request to discover LiDAR sources in a local folder."""

    folder: Path
    recursive: bool = True
    include_ept: bool = True


@dataclass(frozen=True)
class LidarSourceRecord:
    """One discovered LiDAR source and optional inventory metadata."""

    path: Path
    source_type: str
    size_bytes: int
    modified_ns: int
    bounds: Bounds2D | None = None
    crs: str | None = None
    point_count: int | None = None


@dataclass(frozen=True)
class LidarInventory:
    """Discovered source inventory."""

    folder: Path
    sources: tuple[LidarSourceRecord, ...]
    cache_path: Path | None = None


def discover_lidar_sources(request: LidarFolderRequest) -> LidarInventory:
    """Discover supported local LiDAR sources without reading point data."""
    folder = Path(request.folder)
    if not folder.is_dir():
        raise ValueError(f"LiDAR folder does not exist: {folder}")
    iterator: Iterable[Path] = folder.rglob("*") if request.recursive else folder.glob("*")
    sources: list[LidarSourceRecord] = []
    for path in sorted(iterator):
        if not path.is_file():
            continue
        source_type = lidar_source_type(path, include_ept=request.include_ept)
        if source_type is None:
            continue
        stat = path.stat()
        bounds, crs, point_count = _read_ept_metadata(path) if source_type == "ept" else (None, None, None)
        sources.append(LidarSourceRecord(path, source_type, int(stat.st_size), int(stat.st_mtime_ns), bounds=bounds, crs=crs, point_count=point_count))
    return LidarInventory(folder, tuple(sources))


def lidar_source_type(path: Path, *, include_ept: bool = True) -> str | None:
    """Return a supported source type, refusing arbitrary JSON."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    full = str(path).lower()
    if include_ept and name == "ept.json":
        return "ept"
    if full.endswith(".copc.laz"):
        return "copc"
    if suffix in {".las", ".laz", ".copc"}:
        return suffix.lstrip(".")
    return None


def inventory_cache_needs_update(cache_path: Path, inventory: LidarInventory) -> bool:
    """Return whether cache contents differ from current source signatures."""
    if not cache_path.exists():
        return True
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    cached = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(cached, list):
        return True
    current = {str(item.path): (item.size_bytes, item.modified_ns) for item in inventory.sources}
    previous = {str(item.get("path")): (int(item.get("size_bytes", -1)), int(item.get("modified_ns", -1))) for item in cached if isinstance(item, dict)}
    return current != previous


def write_inventory_cache(cache_path: Path, inventory: LidarInventory) -> Path:
    """Write lightweight inventory signatures for rerun detection."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "folder": str(inventory.folder),
        "sources": [
            {
                "path": str(item.path),
                "source_type": item.source_type,
                "size_bytes": item.size_bytes,
                "modified_ns": item.modified_ns,
                "crs": item.crs,
                "point_count": item.point_count,
                "bounds": None if item.bounds is None else item.bounds.__dict__,
            }
            for item in inventory.sources
        ],
    }
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return cache_path



def _read_ept_metadata(path: Path) -> tuple[Bounds2D | None, str | None, int | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None, None
    bounds_value = payload.get("bounds") if isinstance(payload, dict) else None
    bounds = None
    if isinstance(bounds_value, list) and len(bounds_value) >= 4:
        try:
            # EPT commonly stores [xmin, ymin, zmin, xmax, ymax, zmax].
            bounds = Bounds2D(float(bounds_value[0]), float(bounds_value[1]), float(bounds_value[3]), float(bounds_value[4])) if len(bounds_value) >= 5 else None
        except (TypeError, ValueError):
            bounds = None
    srs = payload.get("srs") if isinstance(payload, dict) else None
    crs = None
    if isinstance(srs, dict):
        authority = srs.get("authority")
        horizontal = srs.get("horizontal")
        wkt = srs.get("wkt")
        if isinstance(authority, str) and authority:
            crs = authority
        elif isinstance(horizontal, str) and horizontal:
            crs = horizontal
        elif isinstance(wkt, str) and wkt:
            crs = wkt
    point_count = payload.get("points") if isinstance(payload, dict) else None
    try:
        count = int(point_count) if point_count is not None else None
    except (TypeError, ValueError):
        count = None
    return bounds, crs, count
