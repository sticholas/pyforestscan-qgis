#!/usr/bin/env python3
"""Validate a versioned internal PyForestScan QGIS release build."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

try:
    from package_plugin import (
        BACKEND_MANIFEST_FILE_NAME,
        DEFAULT_LATEST_ZIP_PATH,
        PLUGIN_DIR_NAME,
        RELEASE_MANIFEST_FILE_NAME,
        REPOSITORY_ROOT,
        build_release_manifest,
        read_metadata_version,
        read_version_info,
        sha256_file,
        versioned_zip_path,
    )
    from validate_plugin_package import validate_zip
except ModuleNotFoundError:  # pragma: no cover - used when imported as scripts.validate_release.
    from scripts.package_plugin import (
        BACKEND_MANIFEST_FILE_NAME,
        DEFAULT_LATEST_ZIP_PATH,
        PLUGIN_DIR_NAME,
        RELEASE_MANIFEST_FILE_NAME,
        REPOSITORY_ROOT,
        build_release_manifest,
        read_metadata_version,
        read_version_info,
        sha256_file,
        versioned_zip_path,
    )
    from scripts.validate_plugin_package import validate_zip


FORBIDDEN_ZIP_PARTS = {".git", "__pycache__", "tests", "scripts", ".agents", ".codex"}
FORBIDDEN_ZIP_SUFFIXES = {".pyc", ".pyo"}


def validate_release(dist_dir: Path | None = None, update_manifest: bool = True) -> list[str]:
    """Return release validation errors."""
    errors: list[str] = []
    dist = dist_dir or REPOSITORY_ROOT / "dist"
    version = read_version_info()
    metadata_version = read_metadata_version()
    if metadata_version != version.plugin_version:
        errors.append(f"metadata.txt version {metadata_version} does not match __version__.py {version.plugin_version}.")

    latest_zip = dist / DEFAULT_LATEST_ZIP_PATH.name
    release_zip = versioned_zip_path(version.plugin_version, dist)
    manifest_path = dist / RELEASE_MANIFEST_FILE_NAME
    for required_path, label in ((latest_zip, "latest ZIP"), (release_zip, "versioned ZIP"), (manifest_path, "release manifest")):
        if not required_path.is_file():
            errors.append(f"Missing {label}: {required_path}")
    if errors:
        return errors

    manifest = _read_json(manifest_path)
    errors.extend(_validate_zip_manifest(release_zip, manifest))
    errors.extend(_validate_backend_manifest_hash(release_zip, manifest))
    errors.extend(_validate_package(release_zip))
    errors.extend(_validate_forbidden_members(release_zip))
    errors.extend(_validate_changelog(version.plugin_version))
    errors.extend(_validate_external_worker_disabled())
    errors.extend(_validate_pbm_internal_beta_guard())
    docs_status = _run_docs_link_check()
    if docs_status != "passed" and manifest.get("docs_link_check_status") != "passed":
        errors.append("Documentation link check did not pass and no passing status is recorded.")

    if not errors and update_manifest:
        updated = build_release_manifest(release_zip, validation_status="passed", docs_link_check_status="passed")
        manifest_path.write_text(json.dumps(asdict(updated), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return errors


def _validate_zip_manifest(release_zip: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("zip_filename") != release_zip.name:
        errors.append(f"release_manifest.json zip_filename does not match {release_zip.name}.")
    actual_sha = sha256_file(release_zip)
    if manifest.get("zip_sha256") != actual_sha:
        errors.append("release_manifest.json ZIP SHA256 does not match versioned ZIP.")
    if manifest.get("package_size_bytes") != release_zip.stat().st_size:
        errors.append("release_manifest.json package size does not match versioned ZIP.")
    return errors


def _validate_backend_manifest_hash(release_zip: Path, manifest: dict[str, Any]) -> list[str]:
    source_manifest = REPOSITORY_ROOT / BACKEND_MANIFEST_FILE_NAME
    source_hash = sha256_file(source_manifest)
    errors: list[str] = []
    if manifest.get("backend_manifest_sha256") != source_hash:
        errors.append("release_manifest.json backend manifest SHA256 does not match repository backend_manifest.json.")
    with zipfile.ZipFile(release_zip) as archive:
        member = f"{PLUGIN_DIR_NAME}/{BACKEND_MANIFEST_FILE_NAME}"
        if member not in archive.namelist():
            errors.append(f"ZIP is missing {member}.")
        else:
            import hashlib

            zipped_hash = hashlib.sha256(archive.read(member)).hexdigest()
            if zipped_hash != source_hash:
                errors.append("ZIP backend_manifest.json hash does not match repository backend_manifest.json.")
    return errors


def _validate_package(release_zip: Path) -> list[str]:
    return validate_zip(release_zip)


def _validate_forbidden_members(release_zip: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(release_zip) as archive:
        names = archive.namelist()
    for name in names:
        path = Path(name)
        if set(path.parts) & FORBIDDEN_ZIP_PARTS:
            errors.append(f"Forbidden release member included: {name}")
        if path.suffix in FORBIDDEN_ZIP_SUFFIXES:
            errors.append(f"Forbidden bytecode member included: {name}")
    return errors


def _validate_changelog(version: str) -> list[str]:
    text = (REPOSITORY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return [] if version in text else [f"CHANGELOG.md does not contain an entry for {version}."]


def _validate_external_worker_disabled() -> list[str]:
    pages = (REPOSITORY_ROOT / PLUGIN_DIR_NAME / "ui" / "pages.py").read_text(encoding="utf-8")
    limitations = (REPOSITORY_ROOT / "docs" / "KNOWN_LIMITATIONS.md").read_text(encoding="utf-8")
    if "External Worker is disabled" in pages and "External Worker mode is disabled" in limitations:
        return []
    return ["External Worker disabled guard text was not found."]


def _validate_pbm_internal_beta_guard() -> list[str]:
    pages = (REPOSITORY_ROOT / PLUGIN_DIR_NAME / "ui" / "pages.py").read_text(encoding="utf-8")
    installer = (REPOSITORY_ROOT / PLUGIN_DIR_NAME / "core" / "backend" / "installer.py").read_text(encoding="utf-8")
    version = (REPOSITORY_ROOT / PLUGIN_DIR_NAME / "__version__.py").read_text(encoding="utf-8")
    required = (
        "install_backend_internal_beta" in pages,
        "This will set up all PyForestScan processing components in your user-local PyForestScan folder" in pages,
        "It will not modify QGIS or system Python" in pages,
        "backend_install_availability" in installer,
        "BackendPlatform.WINDOWS" in installer,
        "planned/experimental" in installer,
        "INTERNAL_BETA_BACKEND_INSTALL = True" in version,
    )
    if all(required):
        return []
    return ["PBM internal beta install guard or confirmation text was not found."]


def _run_docs_link_check() -> str:
    completed = subprocess.run((sys.executable, "scripts/check_docs_links.py"), cwd=REPOSITORY_ROOT, check=False, capture_output=True, text=True, timeout=60)
    return "passed" if completed.returncode == 0 else "failed"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=REPOSITORY_ROOT / "dist", help="Directory containing release artifacts.")
    parser.add_argument("--no-update-manifest", action="store_true", help="Validate without rewriting release_manifest.json statuses.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_release(args.dist_dir, update_manifest=not args.no_update_manifest)
    if errors:
        print("Release validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Release validation passed.")
    print(f"Versioned ZIP: {versioned_zip_path(read_version_info().plugin_version, args.dist_dir).resolve()}")
    print(f"Latest ZIP: {(args.dist_dir / DEFAULT_LATEST_ZIP_PATH.name).resolve()}")
    print(f"Release manifest: {(args.dist_dir / RELEASE_MANIFEST_FILE_NAME).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
