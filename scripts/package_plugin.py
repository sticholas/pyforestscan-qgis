#!/usr/bin/env python3
"""Package the PyForestScan QGIS plugin for versioned release distribution."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR_NAME = "pyforestscan_qgis"
BACKEND_SPECS_DIR_NAME = "backend_specs"
BACKEND_MANIFEST_FILE_NAME = "backend_manifest.json"
RELEASE_MANIFEST_FILE_NAME = "release_manifest.json"
DEFAULT_DIST_DIR = REPOSITORY_ROOT / "dist"
DEFAULT_LATEST_ZIP_PATH = DEFAULT_DIST_DIR / f"{PLUGIN_DIR_NAME}.zip"
DEFAULT_ZIP_PATH = DEFAULT_LATEST_ZIP_PATH
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
BUILD_INFO_FILE_NAME = "build_info.json"
PACKAGE_VERIFICATION_FILE_NAME = "package_source_verification.json"
CRITICAL_PLUGIN_MODULES = (
    "plugin.py",
    "metadata.txt",
    "ui/mission_control.py",
    "ui/pages.py",
    "core/polygon_batch.py",
    "core/source_aware_processing.py",
    "core/work_unit_geometry.py",
    "core/polygon_transport.py",
    "core/backend/processing_engine.py",
    "core/adapter.py",
    "core/backend/execution.py",
    "backend_runner/api_contract.py",
    "backend_runner/generic_polygon_coordinator.py",
    "backend_runner/job_coordinator.py",
    "backend_runner/job_result.py",
    "backend_runner/job_spec.py",
    "backend_runner/pbm_lidar_preparation.py",
    "backend_runner/polygon_preparation_worker.py",
    "backend_runner/request_validation.py",
    "backend_runner/run_catalog_job.py",
    "backend_runner/run_processing_job.py",
    "backend_runner/polygon_job_coordinator.py",
    "backend_runner/ept_chm_subread.py",
    "backend_runner/runtime_contract.py",
)
PROCESSING_ENGINE_BUILD_MODULES = (
    "backend_runner/run_processing_job.py",
    "backend_runner/polygon_job_coordinator.py",
    "core/adapter.py",
    "core/pipeline.py",
    "core/backend/execution.py",
    "core/polygon_batch.py",
)

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True)
class VersionInfo:
    """Release version values from the source of truth."""

    plugin_version: str
    build_metadata: str
    minimum_qgis_version: str
    supported_qgis_major_versions: tuple[int, ...]
    compatible_pbm_manifest_version: str
    compatible_pbm_manifest_schema_version: int


@dataclass(frozen=True)
class PackageResult:
    """Paths and metadata produced by package_plugin."""

    versioned_zip_path: Path
    latest_zip_path: Path | None
    release_manifest_path: Path
    version: str
    sha256: str
    verification_path: Path | None = None


@dataclass(frozen=True)
class ReleaseManifest:
    """Trace manifest for one packaged plugin ZIP."""

    plugin_name: str
    plugin_version: str
    git_commit: str
    branch: str
    build_timestamp_utc: str
    zip_filename: str
    zip_sha256: str
    package_size_bytes: int
    pbm_manifest_version: str
    backend_manifest_sha256: str
    python_module_summary: dict[str, Any]
    validation_status: str
    docs_link_check_status: str


def should_include(path: Path, root: Path) -> bool:
    """Return True when a source path should be included in the ZIP."""
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def read_version_info() -> VersionInfo:
    """Load version metadata from pyforestscan_qgis/__version__.py."""
    version_path = REPOSITORY_ROOT / PLUGIN_DIR_NAME / "__version__.py"
    spec = importlib.util.spec_from_file_location("pyforestscan_qgis_version", version_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load version module: {version_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return VersionInfo(
        plugin_version=str(module.PLUGIN_VERSION),
        build_metadata=str(getattr(module, "BUILD_METADATA", "")),
        minimum_qgis_version=str(module.MINIMUM_QGIS_VERSION),
        supported_qgis_major_versions=tuple(int(item) for item in module.SUPPORTED_QGIS_MAJOR_VERSIONS),
        compatible_pbm_manifest_version=str(module.COMPATIBLE_PBM_MANIFEST_VERSION),
        compatible_pbm_manifest_schema_version=int(module.COMPATIBLE_PBM_MANIFEST_SCHEMA_VERSION),
    )


def read_metadata_version(metadata_path: Path | None = None) -> str:
    """Return the version field from QGIS metadata.txt."""
    parser = configparser.ConfigParser()
    path = metadata_path or REPOSITORY_ROOT / PLUGIN_DIR_NAME / "metadata.txt"
    parser.read(path, encoding="utf-8")
    return parser.get("general", "version")


def versioned_zip_path(version: str, dist_dir: Path = DEFAULT_DIST_DIR) -> Path:
    """Return the versioned plugin ZIP path for a release version."""
    return dist_dir / f"{PLUGIN_DIR_NAME}-v{version}.zip"


def package_plugin(
    output_path: Path | None = None,
    latest_path: Path | None = DEFAULT_LATEST_ZIP_PATH,
    write_manifest: bool = True,
    validation_status: str = "pending",
    docs_link_check_status: str = "pending",
    require_clean: bool = False,
) -> PackageResult:
    """Create versioned and latest QGIS-installable plugin ZIPs."""
    plugin_root = REPOSITORY_ROOT / PLUGIN_DIR_NAME
    if not plugin_root.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {plugin_root}")
    if require_clean:
        assert_clean_repository()

    version = read_version_info().plugin_version
    target_path = (output_path or versioned_zip_path(version)).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    _build_plugin_zip(target_path)
    verification_path=target_path.parent/PACKAGE_VERIFICATION_FILE_NAME
    verification=verify_package_source(target_path,require_clean=require_clean)
    verification_path.write_text(json.dumps(verification,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if verification["status"]!="PASS":raise RuntimeError(f"Package/source verification failed: {verification_path}")

    latest_result_path: Path | None = None
    if latest_path is not None:
        latest_result_path = latest_path.resolve()
        latest_result_path.parent.mkdir(parents=True, exist_ok=True)
        if latest_result_path != target_path:
            shutil.copy2(target_path, latest_result_path)

    manifest_path = target_path.parent / RELEASE_MANIFEST_FILE_NAME
    sha256 = sha256_file(target_path)
    if write_manifest:
        manifest = build_release_manifest(
            zip_path=target_path,
            validation_status=validation_status,
            docs_link_check_status=docs_link_check_status,
        )
        manifest_path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return PackageResult(target_path, latest_result_path, manifest_path, version, sha256, verification_path)


def build_release_manifest(zip_path: Path, validation_status: str = "pending", docs_link_check_status: str = "pending") -> ReleaseManifest:
    """Build the trace manifest for a packaged ZIP."""
    version = read_version_info()
    backend_manifest = REPOSITORY_ROOT / BACKEND_MANIFEST_FILE_NAME
    backend_manifest_data = _read_json(backend_manifest)
    return ReleaseManifest(
        plugin_name="PyForestScan",
        plugin_version=version.plugin_version,
        git_commit=_git_value("rev-parse", "HEAD"),
        branch=_git_value("branch", "--show-current"),
        build_timestamp_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        zip_filename=zip_path.name,
        zip_sha256=sha256_file(zip_path),
        package_size_bytes=zip_path.stat().st_size,
        pbm_manifest_version=str(backend_manifest_data.get("backend_version", "unknown")),
        backend_manifest_sha256=sha256_file(backend_manifest),
        python_module_summary=_python_module_summary(zip_path),
        validation_status=validation_status,
        docs_link_check_status=docs_link_check_status,
    )


def sha256_file(path: Path) -> str:
    """Return SHA-256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_plugin_zip(output_path: Path) -> None:
    if output_path.exists():
        output_path.unlink()
    plugin_root = REPOSITORY_ROOT / PLUGIN_DIR_NAME
    with tempfile.TemporaryDirectory(prefix="pyforestscan-package-stage-") as folder:
        stage=Path(folder)/PLUGIN_DIR_NAME
        _copy_clean_tree(plugin_root,stage)
        specs_root = REPOSITORY_ROOT / BACKEND_SPECS_DIR_NAME
        if specs_root.is_dir():
            _copy_clean_tree(specs_root,stage/BACKEND_SPECS_DIR_NAME)
        backend_manifest = REPOSITORY_ROOT / BACKEND_MANIFEST_FILE_NAME
        if backend_manifest.is_file():
            shutil.copy2(backend_manifest,stage/BACKEND_MANIFEST_FILE_NAME)
        (stage/BUILD_INFO_FILE_NAME).write_text(json.dumps(build_package_info(stage),indent=2,sort_keys=True)+"\n",encoding="utf-8")
        with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            _write_tree_to_archive(archive,stage,Path(PLUGIN_DIR_NAME))


def _copy_clean_tree(source: Path,destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True,exist_ok=True)
    for path in sorted(source.rglob("*")):
        if should_include(path,source):
            target=destination/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)


def _write_tree_to_archive(archive: zipfile.ZipFile, source_root: Path, archive_root: Path) -> None:
    """Write all allowed files below source_root to archive_root."""
    for path in sorted(source_root.rglob("*")):
        if not should_include(path, source_root):
            continue
        archive_name = archive_root / path.relative_to(source_root)
        _write_file_to_archive(archive, path, archive_name)


def _write_file_to_archive(archive: zipfile.ZipFile, path: Path, archive_name: Path) -> None:
    """Write one file to the ZIP with deterministic metadata."""
    info = zipfile.ZipInfo(archive_name.as_posix(), FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, path.read_bytes())


def _write_json_to_archive(archive: zipfile.ZipFile, payload: dict[str, Any], archive_name: Path) -> None:
    """Write deterministic JSON metadata generated for this package build."""
    info = zipfile.ZipInfo(archive_name.as_posix(), FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def build_package_info(plugin_root: Path | None = None) -> dict[str, Any]:
    """Build immutable identity metadata embedded inside the plugin ZIP."""
    root = plugin_root or REPOSITORY_ROOT / PLUGIN_DIR_NAME
    hashes = {
        relative: sha256_file(root / relative)
        for relative in CRITICAL_PLUGIN_MODULES
        if (root / relative).is_file()
    }
    identity_payload = {
        "version": read_version_info().plugin_version,
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_state": "clean" if not _git_status() else "dirty",
        "critical_module_hashes": hashes,
        "package_manifest_hash": _manifest_hash(_tree_hashes(root,exclude={BUILD_INFO_FILE_NAME})),
    }
    package_identity = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        **identity_payload,
        "build_id": package_identity[:20],
        "package_identity": package_identity,
        "processing_engine_plugin_build_id": hashlib.sha256(
            b"".join((root / relative).read_bytes() for relative in PROCESSING_ENGINE_BUILD_MODULES)
        ).hexdigest(),
        "package_sha256": "See dist/release_manifest.json; the ZIP cannot contain its own final digest.",
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def expected_package_files() -> dict[str,str]:
    expected={f"{PLUGIN_DIR_NAME}/{path.relative_to(REPOSITORY_ROOT/PLUGIN_DIR_NAME).as_posix()}":sha256_file(path) for path in (REPOSITORY_ROOT/PLUGIN_DIR_NAME).rglob("*") if should_include(path,REPOSITORY_ROOT/PLUGIN_DIR_NAME) and path.name!=BUILD_INFO_FILE_NAME}
    specs=REPOSITORY_ROOT/BACKEND_SPECS_DIR_NAME
    if specs.is_dir():
        expected.update({f"{PLUGIN_DIR_NAME}/{BACKEND_SPECS_DIR_NAME}/{path.relative_to(specs).as_posix()}":sha256_file(path) for path in specs.rglob("*") if should_include(path,specs)})
    manifest=REPOSITORY_ROOT/BACKEND_MANIFEST_FILE_NAME
    if manifest.is_file():expected[f"{PLUGIN_DIR_NAME}/{BACKEND_MANIFEST_FILE_NAME}"]=sha256_file(manifest)
    return expected


def verify_package_source(zip_path: Path,require_clean:bool=True) -> dict[str,Any]:
    expected=expected_package_files()
    with zipfile.ZipFile(zip_path) as archive:
        actual={name:hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if not name.endswith("/")}
        info=json.loads(archive.read(f"{PLUGIN_DIR_NAME}/{BUILD_INFO_FILE_NAME}"))
    generated={f"{PLUGIN_DIR_NAME}/{BUILD_INFO_FILE_NAME}"}
    missing=sorted(set(expected)-set(actual));unexpected=sorted(set(actual)-set(expected)-generated)
    mismatches=sorted(name for name in set(expected)&set(actual) if expected[name]!=actual[name])
    head=_git_value("rev-parse","HEAD")
    identity_errors=[]
    if info.get("git_commit")!=head:identity_errors.append("build identity commit does not match HEAD")
    if require_clean and info.get("git_state")!="clean":identity_errors.append("build identity is not clean")
    return {"schema":"pyforestscan-package-source-verification-v1","status":"PASS" if not (missing or unexpected or mismatches or identity_errors) else "FAIL","git_head":head,"embedded_commit":info.get("git_commit"),"build_id":info.get("build_id"),"source_manifest_count":len(expected),"zip_manifest_count":len(actual),"missing_files":missing,"unexpected_files":unexpected,"hash_mismatches":mismatches,"identity_errors":identity_errors,"critical_module_hashes":info.get("critical_module_hashes",{})}


def assert_clean_repository() -> None:
    status=_git_status()
    if status:raise RuntimeError("Release packaging requires a clean Git worktree. Commit changes or pass the explicit developer override.")


def _git_status() -> str:
    try:return subprocess.run(("git","status","--porcelain"),cwd=REPOSITORY_ROOT,check=False,capture_output=True,text=True,timeout=10).stdout.strip()
    except (OSError,subprocess.SubprocessError):return "unknown"


def _tree_hashes(root: Path,exclude:set[str]|None=None) -> dict[str,str]:
    omitted=exclude or set();return {path.relative_to(root).as_posix():sha256_file(path) for path in root.rglob("*") if path.is_file() and path.name not in omitted and should_include(path,root)}


def _manifest_hash(manifest:dict[str,str]) -> str:
    return hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()


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


def _python_module_summary(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    python_files = [name for name in names if name.endswith(".py")]
    top_level_packages = sorted({Path(name).parts[1] for name in python_files if len(Path(name).parts) > 2})
    return {
        "python_file_count": len(python_files),
        "top_level_package_entries": top_level_packages,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _git_value(*args: str) -> str:
    try:
        completed = subprocess.run(("git", *args), cwd=REPOSITORY_ROOT, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else "unknown"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="ZIP path to create. Defaults to dist/pyforestscan_qgis-v<version>.zip.",
    )
    parser.add_argument(
        "--no-latest",
        action="store_true",
        help="Do not write dist/pyforestscan_qgis.zip as a latest convenience copy.",
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
    parser.add_argument("--allow-dirty",action="store_true",help="Developer-only override for non-release package testing.")
    return parser.parse_args()


def main() -> None:
    """Package the plugin and optionally sync it into QGIS."""
    args = parse_args()
    result = package_plugin(args.output, latest_path=None if args.no_latest else DEFAULT_LATEST_ZIP_PATH,require_clean=not args.allow_dirty)
    print(f"Created versioned plugin ZIP: {result.versioned_zip_path}")
    if result.latest_zip_path is not None:
        print(f"Updated latest plugin ZIP: {result.latest_zip_path}")
    print(f"Wrote release manifest: {result.release_manifest_path}")
    print(f"Wrote source verification: {result.verification_path}")
    print(f"ZIP SHA256: {result.sha256}")

    if args.sync_local:
        destination = sync_plugin(args.qgis_plugin_dir, args.qgis_profile)
        print(f"Synced plugin folder to: {destination}")


if __name__ == "__main__":
    main()
