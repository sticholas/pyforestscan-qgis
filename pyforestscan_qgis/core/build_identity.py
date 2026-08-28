"""Immutable packaged-build identity and cheap installed-file integrity checks."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BUILD_INFO_NAME = "build_info.json"
CRITICAL_MODULES = (
    "plugin.py",
    "ui/mission_control.py",
    "core/polygon_batch.py",
    "core/backend/processing_engine.py",
    "core/adapter.py",
    "core/backend/execution.py",
    "backend_runner/run_processing_job.py",
    "backend_runner/polygon_job_coordinator.py",
)
PLUGIN_VALID = "PLUGIN_VALID"
PLUGIN_MIXED_INSTALL = "PLUGIN_MIXED_INSTALL"
PLUGIN_CORRUPT = "PLUGIN_CORRUPT"
PLUGIN_UNKNOWN = "PLUGIN_UNKNOWN"


@dataclass(frozen=True)
class PluginInstallationIdentity:
    """One installed plugin build and its local integrity result."""

    status: str
    version: str
    git_commit: str
    build_id: str
    built_at: str
    package_identity: str
    processing_engine_plugin_build_id: str
    plugin_root: Path
    expected_hashes: dict[str, str]
    actual_hashes: dict[str, str]
    mismatches: tuple[str, ...] = ()
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "version": self.version,
            "git_commit": self.git_commit,
            "build_id": self.build_id,
            "built_at": self.built_at,
            "package_identity": self.package_identity,
            "processing_engine_plugin_build_id": self.processing_engine_plugin_build_id,
            "plugin_root": str(self.plugin_root),
            "expected_hashes": dict(self.expected_hashes),
            "actual_hashes": dict(self.actual_hashes),
            "mismatches": list(self.mismatches),
            "message": self.message,
        }


_SESSION_IDENTITY: PluginInstallationIdentity | None = None


def plugin_root() -> Path:
    """Return the root of the plugin code imported by this Python process."""
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def critical_module_hashes(root: Path | None = None) -> dict[str, str]:
    """Hash critical launch modules without importing QGIS or scientific packages."""
    base = Path(root or plugin_root()).resolve()
    return {
        relative: sha256_file(base / relative)
        for relative in CRITICAL_MODULES
        if (base / relative).is_file()
    }


def inspect_plugin_installation(root: Path | None = None) -> PluginInstallationIdentity:
    """Compare loaded plugin files with package-time build metadata."""
    base = Path(root or plugin_root()).resolve()
    info_path = base / BUILD_INFO_NAME
    if not info_path.is_file():
        return PluginInstallationIdentity(
            PLUGIN_UNKNOWN, "unknown", "unknown", "development", "", "development", "unknown",
            base, {}, critical_module_hashes(base), (),
            "Packaged build metadata is unavailable. Install a packaged plugin ZIP.",
        )
    try:
        payload = json.loads(info_path.read_text(encoding="utf-8"))
        expected = {str(key): str(value) for key, value in dict(payload["critical_module_hashes"]).items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return PluginInstallationIdentity(
            PLUGIN_CORRUPT, "unknown", "unknown", "unknown", "", "unknown", "unknown",
            base, {}, critical_module_hashes(base), (BUILD_INFO_NAME,),
            f"Packaged build metadata is invalid: {exc}",
        )
    actual = critical_module_hashes(base)
    mismatches = tuple(sorted(name for name, digest in expected.items() if actual.get(name) != digest))
    status = PLUGIN_MIXED_INSTALL if mismatches else PLUGIN_VALID
    message = (
        "PyForestScan plugin files do not match this installed build. Reinstall the plugin ZIP."
        if mismatches else f"Installed plugin matches build {payload.get('build_id', 'unknown')}."
    )
    return PluginInstallationIdentity(
        status=status,
        version=str(payload.get("version", "unknown")),
        git_commit=str(payload.get("git_commit", "unknown")),
        build_id=str(payload.get("build_id", "unknown")),
        built_at=str(payload.get("built_at", "")),
        package_identity=str(payload.get("package_identity", payload.get("build_id", "unknown"))),
        processing_engine_plugin_build_id=str(payload.get("processing_engine_plugin_build_id", "unknown")),
        plugin_root=base,
        expected_hashes=expected,
        actual_hashes=actual,
        mismatches=mismatches,
        message=message,
    )


def session_identity() -> PluginInstallationIdentity:
    """Return the immutable identity captured when this plugin session began."""
    global _SESSION_IDENTITY
    if _SESSION_IDENTITY is None:
        _SESSION_IDENTITY = inspect_plugin_installation()
    return _SESSION_IDENTITY


def verify_session_files_unchanged() -> PluginInstallationIdentity:
    """Reject files replaced beneath a running QGIS process."""
    captured = session_identity()
    current = inspect_plugin_installation(captured.plugin_root)
    if current.build_id != captured.build_id or current.actual_hashes != captured.actual_hashes:
        mismatches = tuple(sorted(set(current.mismatches) | set(captured.actual_hashes) | set(current.actual_hashes)))
        return PluginInstallationIdentity(
            PLUGIN_MIXED_INSTALL, captured.version, captured.git_commit, captured.build_id,
            captured.built_at, captured.package_identity, captured.processing_engine_plugin_build_id, captured.plugin_root,
            captured.expected_hashes, current.actual_hashes, mismatches,
            "Plugin files changed while QGIS is running. Restart QGIS.",
        )
    return current


def write_plugin_session_identity(target: Path | None = None) -> Path:
    """Regenerate the current-session identity trace."""
    identity = session_identity()
    destination = target or _default_session_identity_path()
    payload = identity.to_dict()
    payload.update({
        "qgis_version": _qgis_version(),
        "python_version": platform.python_version(),
        "plugin_version": identity.version,
        "plugin_build_id": identity.build_id,
        "plugin_file_path": str((identity.plugin_root / "plugin.py").resolve()),
        "loaded_module_paths": _loaded_module_paths(identity.plugin_root),
        "process_id": os.getpid(),
        "profile_path": _qgis_profile_path(),
        "loaded_at": _utc_now(),
    })
    _write_json(destination, payload)
    return destination


def _loaded_module_paths(root: Path) -> dict[str, str]:
    return {
        "plugin.py": str((root / "plugin.py").resolve()),
        "mission_control.py": str((root / "ui/mission_control.py").resolve()),
        "polygon_batch.py": str((root / "core/polygon_batch.py").resolve()),
        "processing_engine_service.py": str((root / "core/backend/processing_engine.py").resolve()),
        "adapter.py": str((root / "core/adapter.py").resolve()),
        "managed_launcher.py": str((root / "core/backend/execution.py").resolve()),
        "polygon_job_coordinator.py": str((root / "backend_runner/polygon_job_coordinator.py").resolve()),
    }


def _default_session_identity_path() -> Path:
    from .backend.paths import resolve_backend_paths
    return resolve_backend_paths().backend_root / "diagnostics" / "plugin_session_identity.json"


def _qgis_version() -> str:
    try:
        from qgis.core import Qgis
        return str(Qgis.QGIS_VERSION)
    except Exception:
        return "unavailable"


def _qgis_profile_path() -> str:
    try:
        from qgis.core import QgsApplication
        return str(QgsApplication.qgisSettingsDirPath())
    except Exception:
        return "unavailable"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
