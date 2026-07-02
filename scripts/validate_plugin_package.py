#!/usr/bin/env python3
"""Validate a packaged PyForestScan QGIS plugin ZIP."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR_NAME = "pyforestscan_qgis"
DEFAULT_ZIP_PATH = REPOSITORY_ROOT / "dist" / f"{PLUGIN_DIR_NAME}.zip"

REQUIRED_FILES = {
    f"{PLUGIN_DIR_NAME}/metadata.txt",
    f"{PLUGIN_DIR_NAME}/__init__.py",
    f"{PLUGIN_DIR_NAME}/plugin.py",
    f"{PLUGIN_DIR_NAME}/provider.py",
    f"{PLUGIN_DIR_NAME}/processing_provider.py",
    f"{PLUGIN_DIR_NAME}/icons/pyforestscan.svg",
    f"{PLUGIN_DIR_NAME}/backend_specs/environment.yml",
    f"{PLUGIN_DIR_NAME}/backend_specs/environment.windows.yml",
    f"{PLUGIN_DIR_NAME}/backend_specs/environment.linux.yml",
    f"{PLUGIN_DIR_NAME}/backend_specs/environment.macos.yml",
    f"{PLUGIN_DIR_NAME}/backend_specs/pins.md",
}

FORBIDDEN_PARTS = {".git", "__pycache__"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}


def validate_zip(zip_path: Path = DEFAULT_ZIP_PATH) -> list[str]:
    """Return validation errors for a plugin ZIP."""
    errors: list[str] = []
    if not zip_path.is_file():
        return [f"ZIP does not exist: {zip_path}"]

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()

    name_set = set(names)
    for required in sorted(REQUIRED_FILES):
        if required not in name_set:
            errors.append(f"Missing required file: {required}")

    for name in names:
        path = Path(name)
        parts = set(path.parts)
        if not name.startswith(f"{PLUGIN_DIR_NAME}/"):
            errors.append(f"Unexpected top-level path: {name}")
        if parts & FORBIDDEN_PARTS:
            errors.append(f"Forbidden directory included: {name}")
        if path.suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"Forbidden compiled Python file included: {name}")

    if f"{PLUGIN_DIR_NAME}/" in name_set:
        errors.append("ZIP should contain files under pyforestscan_qgis/, not an explicit empty root entry.")

    return errors


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "zip_path",
        nargs="?",
        type=Path,
        default=DEFAULT_ZIP_PATH,
        help="Plugin ZIP to validate. Defaults to dist/pyforestscan_qgis.zip.",
    )
    return parser.parse_args()


def main() -> int:
    """Validate the requested plugin ZIP."""
    args = parse_args()
    errors = validate_zip(args.zip_path)
    if errors:
        print("Plugin package validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Plugin package validation passed: {args.zip_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
