#!/usr/bin/env python3
"""Print dry-run GitHub release preparation details."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from package_plugin import DEFAULT_DIST_DIR, RELEASE_MANIFEST_FILE_NAME, REPOSITORY_ROOT, read_version_info, sha256_file, versioned_zip_path
except ModuleNotFoundError:  # pragma: no cover - used when imported as scripts.prepare_github_release.
    from scripts.package_plugin import DEFAULT_DIST_DIR, RELEASE_MANIFEST_FILE_NAME, REPOSITORY_ROOT, read_version_info, sha256_file, versioned_zip_path


def release_notes_path(version: str) -> Path:
    """Return the release notes path for a version."""
    return REPOSITORY_ROOT / "docs" / "releases" / f"v{version}.md"


def prepare_release(dist_dir: Path = DEFAULT_DIST_DIR) -> dict[str, str]:
    """Return release preparation values without creating a GitHub release."""
    version = read_version_info().plugin_version
    zip_path = versioned_zip_path(version, dist_dir)
    manifest_path = dist_dir / RELEASE_MANIFEST_FILE_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    commit = str(manifest.get("git_commit", "unknown"))
    return {
        "version": version,
        "tag_name": f"v{version}",
        "commit": commit,
        "release_title": f"PyForestScan QGIS v{version}",
        "release_notes_path": str(release_notes_path(version)),
        "zip_artifact_path": str(zip_path),
        "sha256": sha256_file(zip_path) if zip_path.exists() else "missing",
    }


def print_dry_run(values: dict[str, str]) -> None:
    """Print a dry-run release summary and suggested gh commands."""
    print("GitHub release dry run")
    for key in ("version", "tag_name", "commit", "release_title", "release_notes_path", "zip_artifact_path", "sha256"):
        print(f"{key}: {values[key]}")
    print("")
    print("Suggested gh CLI commands:")
    print(f"git tag -a {values['tag_name']} {values['commit']} -m \"{values['release_title']}\"")
    print(f"git push origin {values['tag_name']}")
    print(
        "gh release create "
        f"{values['tag_name']} {values['zip_artifact_path']} "
        f"--title \"{values['release_title']}\" "
        f"--notes-file {values['release_notes_path']} "
        "--draft"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print release details without creating anything. Required for now.")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR, help="Directory containing release artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("Only --dry-run is supported. GitHub releases are not created automatically.", file=sys.stderr)
        return 2
    print_dry_run(prepare_release(args.dist_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
