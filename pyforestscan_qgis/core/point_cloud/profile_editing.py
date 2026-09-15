"""Validated editing operations for source-space profile paths."""
from __future__ import annotations

import math


def _point(value):
    point = tuple(float(v) for v in value)
    if len(point) != 2 or not all(math.isfinite(v) for v in point):
        raise ValueError("Profile vertices must contain two finite source coordinates.")
    return point


def normalize_path(points, *, minimum=2, maximum=256):
    path = tuple(_point(point) for point in points)
    if not minimum <= len(path) <= maximum:
        raise ValueError(f"Profile paths require {minimum}-{maximum} vertices.")
    if any(a == b for a, b in zip(path, path[1:])):
        raise ValueError("Profile vertices must not repeat consecutively.")
    return path


def move_vertex(points, index, point):
    path = list(normalize_path(points))
    if not 0 <= index < len(path):
        raise IndexError("Profile vertex index is out of range.")
    path[index] = _point(point)
    return normalize_path(path)


def insert_vertex(points, index, point):
    path = list(normalize_path(points))
    if not 0 < index < len(path):
        raise IndexError("Inserted vertices must be between the two endpoints.")
    path.insert(index, _point(point))
    return normalize_path(path)


def remove_vertex(points, index):
    path = list(normalize_path(points))
    if not 0 < index < len(path) - 1:
        raise ValueError("Only intermediate profile vertices can be removed.")
    path.pop(index)
    return normalize_path(path)


def insert_midpoint(points, segment_index):
    path = normalize_path(points)
    if not 0 <= segment_index < len(path) - 1:
        raise IndexError("Profile segment index is out of range.")
    a, b = path[segment_index], path[segment_index + 1]
    return insert_vertex(path, segment_index + 1,
                         ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))


def replace_path(geometry, points):
    path = normalize_path(points)
    updated = dict(geometry)
    updated["a"], updated["b"] = path[0], path[-1]
    updated["path"] = path
    return updated
