"""Backend/plugin version compatibility helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .manifest import BackendManifest


@dataclass(frozen=True)
class VersionCompatibilityResult:
    """Compatibility result for one plugin/backend pair."""

    compatible: bool
    plugin_version: str
    backend_version: str
    message: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class BackendVersionManager:
    """Compare versions and detect plugin/backend mismatches."""

    def __init__(self, plugin_version: str) -> None:
        self.plugin_version = plugin_version

    def compare_versions(self, left: str, right: str) -> int:
        """Return -1, 0, or 1 for simple semantic-ish version strings."""
        left_parts = _version_parts(left)
        right_parts = _version_parts(right)
        width = max(len(left_parts), len(right_parts))
        left_parts += (0,) * (width - len(left_parts))
        right_parts += (0,) * (width - len(right_parts))
        if left_parts < right_parts:
            return -1
        if left_parts > right_parts:
            return 1
        return 0

    def check_manifest(self, manifest: BackendManifest) -> VersionCompatibilityResult:
        """Check whether the plugin version is compatible with a backend manifest."""
        errors: list[str] = []
        warnings: list[str] = []
        if self.compare_versions(self.plugin_version, manifest.minimum_plugin_version) < 0:
            errors.append(f"Plugin {self.plugin_version} is older than minimum supported {manifest.minimum_plugin_version}.")
        if manifest.maximum_plugin_version and self.compare_versions(self.plugin_version, manifest.maximum_plugin_version) > 0:
            errors.append(f"Plugin {self.plugin_version} is newer than maximum supported {manifest.maximum_plugin_version}.")
        if manifest.future_migration_version and self.compare_versions(manifest.backend_version, manifest.future_migration_version) >= 0:
            warnings.append("Backend manifest declares a future migration boundary; upgrade handling must run before activation.")
        if not manifest.micromamba_artifact().sha256_for_platforms_present():
            warnings.append("Micromamba checksums are not fully pinned; public installation should remain disabled.")
        compatible = not errors
        message = "Backend manifest is compatible with this plugin." if compatible else "Backend manifest is not compatible with this plugin."
        return VersionCompatibilityResult(compatible, self.plugin_version, manifest.backend_version, message, tuple(warnings), tuple(errors))

    def needs_migration(self, installed_backend_version: str, manifest: BackendManifest) -> bool:
        """Return whether the installed backend is older than the manifest backend."""
        return self.compare_versions(installed_backend_version, manifest.backend_version) < 0

    def can_downgrade(self, installed_backend_version: str, target_backend_version: str) -> bool:
        """Return False for now; downgrades require an explicit future plan."""
        return self.compare_versions(installed_backend_version, target_backend_version) > 0 and False


def _version_parts(value: str) -> tuple[int, ...]:
    numbers = [int(item) for item in re.findall(r"\d+", value)]
    return tuple(numbers or [0])
