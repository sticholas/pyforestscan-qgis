"""Micromamba bootstrap policy for the managed backend installer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .checksums import ChecksumPolicy
from .models import BackendPlatform
from .paths import BackendPaths

MICROMAMBA_BASE_URL = "https://micro.mamba.pm/api/micromamba"

_PLATFORM_SUBDIRS = {
    BackendPlatform.WINDOWS: "win-64",
    BackendPlatform.LINUX: "linux-64",
    BackendPlatform.MACOS: "osx-64",
}

_ARCHIVE_NAMES = {
    BackendPlatform.WINDOWS: "micromamba-win-64.tar.bz2",
    BackendPlatform.LINUX: "micromamba-linux-64.tar.bz2",
    BackendPlatform.MACOS: "micromamba-osx-64.tar.bz2",
    BackendPlatform.UNKNOWN: "micromamba-unknown.tar.bz2",
}


@dataclass(frozen=True)
class MicromambaBootstrapPolicy:
    """Resolved Micromamba bootstrap source and local paths."""

    platform: BackendPlatform
    source_url: str
    archive_name: str
    download_path: Path
    executable_path: Path
    checksum_policy: ChecksumPolicy
    retry_count: int = 2
    notes: tuple[str, ...] = ()


def micromamba_source_url(platform: BackendPlatform, version: str = "latest") -> str:
    """Return the official Micromamba API URL for a supported platform."""
    subdir = _PLATFORM_SUBDIRS.get(platform)
    if subdir is None:
        return ""
    return f"{MICROMAMBA_BASE_URL}/{subdir}/{version}"


def micromamba_archive_name(platform: BackendPlatform) -> str:
    """Return the local archive name used in the PBM download cache."""
    return _ARCHIVE_NAMES.get(platform, _ARCHIVE_NAMES[BackendPlatform.UNKNOWN])


def micromamba_bootstrap_policy(paths: BackendPaths, checksum: str | None = None) -> MicromambaBootstrapPolicy:
    """Build the bootstrap policy for the current backend paths."""
    source_url = micromamba_source_url(paths.platform)
    archive_name = micromamba_archive_name(paths.platform)
    notes = [
        "Micromamba is downloaded only into the user-local PBM downloads directory.",
        "Checksum verification is enforced when a pinned SHA-256 is supplied by the manifest.",
        "Internal beta builds may proceed without a checksum while logging that verification was skipped.",
        "Offline installation remains a future placeholder for pre-fetched artifacts and lock files.",
    ]
    if not source_url:
        notes.append("Unsupported platform; no Micromamba source URL is selected.")
    return MicromambaBootstrapPolicy(
        platform=paths.platform,
        source_url=source_url,
        archive_name=archive_name,
        download_path=paths.downloads_dir / archive_name,
        executable_path=paths.micromamba_executable,
        checksum_policy=ChecksumPolicy(expected=checksum, required=bool(checksum), source="Pinned SHA-256 supplied by installer policy when available."),
        notes=tuple(notes),
    )
