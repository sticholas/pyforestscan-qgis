#!/usr/bin/env python3
"""Package the PyForestScan QGIS plugin for local QGIS installation."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR_NAME = "pyforestscan_qgis"
BACKEND_SPECS_DIR_NAME = "backend_specs"
BACKEND_MANIFEST_FILE_NAME = "backend_manifest.json"
DEFAULT_DIST_DIR = REPOSITORY_ROOT / "dist"
DEFAULT_ZIP_PATH = DEFAULT_DIST_DIR / f"{PLUGIN_DIR_NAME}.zip"

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path, root: Path) -> bool:
    """Return True when a source path should be included in the ZIP."""
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def _write_tree_to_archive(archive: zipfile.ZipFile, source_root: Path, archive_root: Path) -> None:
    """Write all allowed files below source_root to archive_root."""
    for path in sorted(source_root.rglob("*")):
        if not should_include(path, source_root):
            continue
        archive_name = archive_root / path.relative_to(source_root)
        archive.write(path, archive_name.as_posix())


def package_plugin(output_path: Path = DEFAULT_ZIP_PATH) -> Path:
    """Create a QGIS-installable plugin ZIP and return its path."""
    plugin_root = REPOSITORY_ROOT / PLUGIN_DIR_NAME
    if not plugin_root.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {plugin_root}")

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_tree_to_archive(archive, plugin_root, Path(PLUGIN_DIR_NAME))
        specs_root = REPOSITORY_ROOT / BACKEND_SPECS_DIR_NAME
        if specs_root.is_dir():
            _write_tree_to_archive(archive, specs_root, Path(PLUGIN_DIR_NAME) / BACKEND_SPECS_DIR_NAME)
        manifest_path = REPOSITORY_ROOT / BACKEND_MANIFEST_FILE_NAME
        if manifest_path.is_file():
            archive.write(manifest_path, (Path(PLUGIN_DIR_NAME) / BACKEND_MANIFEST_FILE_NAME).as_posix())

    return output_path


def qgis_plugin_directory(profile: str = "default") -> Path:
    """Return the likely QGIS plugin directory for the current platform."""
    home = Path.home()
    return home / ".local" / "share" / "QGIS" / "QGIS3" / "profiles" / profile / "python" / "plugins"


def sync_plugin(target_dir: Path | None = None, profile: str = "default") -> Path:
    """Copy the plugin folder into a local QGIS profile plugin directory."""
    plugin_root = REPOSITORY_ROOT / PLUGIN_DIR_NAME
    destination_parent = target_dir or qgis_plugin_directory(profile)
    destination = destination_parent / PLUGIN_DIR_NAME

    if destination.exists():
        shutil.rmtree(destination)
    destination_parent.mkdir(parents=True, exist_ok=True)

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            candidate = Path(directory) / name
            if name in EXCLUDED_DIR_NAMES or candidate.suffix in EXCLUDED_SUFFIXES:
                ignored.add(name)
        return ignored

    shutil.copytree(plugin_root, destination, ignore=ignore)
    specs_root = REPOSITORY_ROOT / BACKEND_SPECS_DIR_NAME
    if specs_root.is_dir():
        shutil.copytree(specs_root, destination / BACKEND_SPECS_DIR_NAME, ignore=ignore)
    manifest_path = REPOSITORY_ROOT / BACKEND_MANIFEST_FILE_NAME
    if manifest_path.is_file():
        shutil.copy2(manifest_path, destination / BACKEND_MANIFEST_FILE_NAME)
    return destination


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ZIP_PATH,
        help="ZIP path to create. Defaults to dist/pyforestscan_qgis.zip.",
    )
    parser.add_argument(
        "--sync-local",
        action="store_true",
        help="Also copy the plugin folder into the local QGIS plugin directory.",
    )
    parser.add_argument(
        "--qgis-profile",
        default="default",
        help="QGIS profile name used with --sync-local. Defaults to default.",
    )
    parser.add_argument(
        "--qgis-plugin-dir",
        type=Path,
        default=None,
        help="Explicit QGIS plugins directory used with --sync-local.",
    )
    return parser.parse_args()


def main() -> None:
    """Package the plugin and optionally sync it into QGIS."""
    args = parse_args()
    zip_path = package_plugin(args.output)
    print(f"Created plugin ZIP: {zip_path}")

    if args.sync_local:
        destination = sync_plugin(args.qgis_plugin_dir, args.qgis_profile)
        print(f"Synced plugin folder to: {destination}")


if __name__ == "__main__":
    main()
