"""Small, fail-open EPT hierarchy occupancy index for sparse planning."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class EptOccupancy:
    depth: int
    boxes: tuple[tuple[float, float, float, float], ...]
    record_count: int

    def intersects(self, extent) -> bool:
        return any(not (extent.xmax <= box[0] or extent.xmin >= box[2] or extent.ymax <= box[1] or extent.ymin >= box[3]) for box in self.boxes)


def load_ept_occupancy(source: Path | str, maximum_depth: int = 5) -> EptOccupancy | None:
    """Read only root EPT metadata/hierarchy; unavailable metadata never blocks work."""
    path = Path(source)
    try:
        stat = path.stat()
        hierarchy = path.parent / "ept-hierarchy" / "0-0-0-0.json"
        hierarchy_stat = hierarchy.stat()
    except OSError:
        return None
    try:
        return _load(str(path), stat.st_size, stat.st_mtime_ns, str(hierarchy), hierarchy_stat.st_size, hierarchy_stat.st_mtime_ns, maximum_depth)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


@lru_cache(maxsize=16)
def _load(metadata_path: str, _metadata_size: int, _metadata_mtime: int, hierarchy_path: str, _hierarchy_size: int, _hierarchy_mtime: int, maximum_depth: int) -> EptOccupancy | None:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    hierarchy = json.loads(Path(hierarchy_path).read_text(encoding="utf-8"))
    bounds = metadata.get("bounds")
    if not isinstance(bounds, list) or len(bounds) < 6 or not isinstance(hierarchy, dict):
        return None
    parsed = []
    for key, count in hierarchy.items():
        try:
            depth, x, y, _z = (int(value) for value in key.split("-"))
            if depth <= maximum_depth and int(count) != 0:
                parsed.append((depth, x, y))
        except (ValueError, TypeError):
            continue
    if not parsed:
        return None
    depth = max(item[0] for item in parsed)
    side = max(float(bounds[3]) - float(bounds[0]), float(bounds[4]) - float(bounds[1]), float(bounds[5]) - float(bounds[2]))
    width = side / (2 ** depth)
    boxes = tuple(
        (float(bounds[0]) + x * width, float(bounds[1]) + y * width, float(bounds[0]) + (x + 1) * width, float(bounds[1]) + (y + 1) * width)
        for item_depth, x, y in parsed if item_depth == depth
    )
    return EptOccupancy(depth, boxes, len(hierarchy)) if boxes else None
