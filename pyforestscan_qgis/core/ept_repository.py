"""EPT repository normalization and catalog-safety helpers."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .lidar_catalog import connect_catalog, upsert_records
from .lidar_catalog_models import LidarCatalogRecord, default_lidar_catalog_path, stable_root_id

EPT_DATA_DIRS = {"ept-data", "ept-hierarchy"}
EPT_SUPPORT_FILES = {"ept-build.json", "ept-sources.json"}


@dataclass(frozen=True)
class EptSelection:
    """Normalized EPT selection result."""

    input_path: Path
    ept_root: Path
    ept_json: Path
    normalized_repository: Path
    detected: bool
    message: str = ""


@dataclass(frozen=True)
class EptCatalogRepairReport:
    """Result from fast incorrect EPT catalog repair."""

    catalog_path: Path
    backup_path: Path | None
    repaired: bool
    logical_source_path: Path | None
    removed_internal_records: int
    message: str


def resolve_ept_selection(path: str | Path) -> EptSelection | None:
    """Resolve ept.json, an EPT root, or an internal EPT folder to the logical EPT dataset."""
    raw = Path(path).expanduser()
    candidate = raw.resolve() if raw.exists() else raw.absolute()
    if candidate.is_file() and candidate.name.lower() == "ept.json":
        root = candidate.parent
        return EptSelection(raw, root, candidate, root, True, "EPT metadata selected. Using the EPT dataset root.")
    if candidate.is_dir() and (candidate / "ept.json").is_file():
        return EptSelection(raw, candidate, candidate / "ept.json", candidate, True, "EPT dataset root detected.")
    parts_lower = [part.lower() for part in candidate.parts]
    for marker in EPT_DATA_DIRS:
        if marker in parts_lower:
            index = parts_lower.index(marker)
            root = Path(*candidate.parts[:index]) if index > 0 else candidate.anchor
            ept_json = root / "ept.json"
            if ept_json.is_file():
                return EptSelection(raw, root, ept_json, root, True, "EPT data folder detected. Using its parent EPT dataset.")
    for parent in (candidate, *candidate.parents):
        ept_json = parent / "ept.json"
        if ept_json.is_file() and _is_relative_to(candidate, parent):
            return EptSelection(raw, parent, ept_json, parent, True, "EPT hierarchy detected. Using the parent EPT dataset.")
    return None


def is_ept_internal_path(path: str | Path) -> bool:
    """Return whether a path is inside EPT internals and should not be cataloged as a source."""
    return any(part.lower() in EPT_DATA_DIRS for part in Path(path).parts)


def prune_ept_traversal(current: Path, dirnames: list[str], filenames: list[str]) -> list[Path]:
    """Prune EPT internals during os.walk and return logical ept.json sources to inspect."""
    logical_sources: list[Path] = []
    if "ept.json" in {name.lower() for name in filenames}:
        ept_json = current / next(name for name in filenames if name.lower() == "ept.json")
        logical_sources.append(ept_json)
        blocked = {name.lower() for name in EPT_DATA_DIRS}
        dirnames[:] = [name for name in dirnames if name.lower() not in blocked]
    return logical_sources


def incorrect_ept_catalog_detected(catalog_path: Path | str, root_path: Path | str) -> bool:
    """Return whether a catalog appears to index internal EPT nodes individually."""
    catalog = Path(catalog_path)
    if not catalog.exists():
        return False
    root = Path(root_path).expanduser().resolve()
    if resolve_ept_selection(root) is None:
        return False
    root_id = stable_root_id(root)
    connection = connect_catalog(catalog)
    try:
        total = connection.execute("SELECT COUNT(*) AS count FROM lidar_sources WHERE root_id = ?", (root_id,)).fetchone()["count"] or 0
        internal = connection.execute(
            "SELECT COUNT(*) AS count FROM lidar_sources WHERE root_id = ? AND (relative_path LIKE 'ept-data/%' OR relative_path LIKE 'ept-hierarchy/%' OR relative_path LIKE '%/ept-data/%' OR relative_path LIKE '%/ept-hierarchy/%')",
            (root_id,),
        ).fetchone()["count"] or 0
    finally:
        connection.close()
    return int(internal) > 0 and (int(total) > 100 or int(internal) >= max(1, int(total) // 2))


def repair_ept_catalog(catalog_path: Path | str, root_path: Path | str, *, backup: bool = True) -> EptCatalogRepairReport:
    """Repair an incorrect node-level EPT catalog without traversing EPT internals."""
    root = Path(root_path).expanduser().resolve()
    selection = resolve_ept_selection(root)
    if selection is None:
        return EptCatalogRepairReport(Path(catalog_path), None, False, None, 0, "No EPT dataset was detected for this repository.")
    catalog = Path(catalog_path)
    backup_path = None
    if backup and catalog.exists():
        backup_path = catalog.with_suffix(catalog.suffix + ".ept-node-backup")
        shutil.copy2(catalog, backup_path)
    from .lidar_catalog_builder import inspect_lidar_header

    root_id = stable_root_id(selection.normalized_repository)
    record = inspect_lidar_header(selection.ept_json, selection.normalized_repository, root_id)
    connection = connect_catalog(catalog)
    try:
        rows = connection.execute(
            "SELECT id FROM lidar_sources WHERE root_id = ? AND (relative_path LIKE 'ept-data/%' OR relative_path LIKE 'ept-hierarchy/%' OR relative_path LIKE '%/ept-data/%' OR relative_path LIKE '%/ept-hierarchy/%')",
            (root_id,),
        ).fetchall()
        ids = [int(row["id"]) for row in rows]
        connection.executemany("DELETE FROM lidar_source_bounds WHERE id = ?", ((item,) for item in ids))
        connection.executemany("DELETE FROM lidar_sources WHERE id = ?", ((item,) for item in ids))
        upsert_records(connection, (record,))
        connection.commit()
    finally:
        connection.close()
    return EptCatalogRepairReport(catalog, backup_path, True, selection.ept_json, len(ids), "Incorrect EPT catalog repaired: one logical ept.json source is registered.")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
