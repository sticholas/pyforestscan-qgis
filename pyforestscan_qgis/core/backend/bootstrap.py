"""Micromamba bootstrap planning for PBM dry runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import BackendPlatform
from .paths import BackendPaths


@dataclass(frozen=True)
class MicromambaBootstrapPlan:
    """Dry-run description of the future micromamba bootstrap artifact."""

    platform: BackendPlatform
    target_executable: Path
    download_cache_path: Path
    artifact_name: str
    source_note: str
    verification_steps: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def build_micromamba_bootstrap_plan(paths: BackendPaths) -> MicromambaBootstrapPlan:
    """Return the planned micromamba bootstrap layout without downloading anything."""
    artifact = _artifact_name(paths.platform)
    warnings: list[str] = []
    if paths.platform is BackendPlatform.UNKNOWN:
        warnings.append("Host platform is unknown; micromamba artifact selection must be resolved before installation is enabled.")
    return MicromambaBootstrapPlan(
        platform=paths.platform,
        target_executable=paths.micromamba_executable,
        download_cache_path=paths.downloads_dir / artifact,
        artifact_name=artifact,
        source_note="Future installer will use a pinned micromamba bootstrap source with checksum verification. No download occurs in Phase 22B.",
        verification_steps=(
            "Verify downloaded artifact checksum before extraction.",
            "Verify micromamba executable exists at the user-local backend path.",
            "Run micromamba --version from the managed backend path.",
        ),
        warnings=tuple(warnings),
    )


def _artifact_name(platform: BackendPlatform) -> str:
    if platform is BackendPlatform.WINDOWS:
        return "micromamba-win-64-placeholder.tar.bz2"
    if platform is BackendPlatform.MACOS:
        return "micromamba-osx-64-or-arm64-placeholder.tar.bz2"
    if platform is BackendPlatform.LINUX:
        return "micromamba-linux-64-placeholder.tar.bz2"
    return "micromamba-unknown-platform-placeholder.tar.bz2"
