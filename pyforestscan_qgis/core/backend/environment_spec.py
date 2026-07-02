"""Dry-run environment specification for the managed PyForestScan backend."""

from __future__ import annotations

from dataclasses import dataclass

from .models import BackendDependency, BackendRegistry
from .registry import default_backend_registry

_REQUIRED_ENV_PACKAGES = ("python", "pyforestscan", "pdal", "python-pdal", "gdal", "rasterio", "numpy")


@dataclass(frozen=True)
class BackendEnvironmentPackage:
    """One package planned for the managed backend environment."""

    name: str
    display_name: str
    version_spec: str
    source: str
    category: str
    registry_required: bool
    python_import_name: str | None = None
    executable_name: str | None = None

    @classmethod
    def from_dependency(cls, dependency: BackendDependency) -> "BackendEnvironmentPackage":
        """Create an environment package from the dependency registry."""
        return cls(
            name=dependency.name,
            display_name=dependency.display_name,
            version_spec=dependency.version_spec,
            source=dependency.source,
            category=dependency.category,
            registry_required=dependency.required,
            python_import_name=dependency.python_import_name,
            executable_name=dependency.executable_name,
        )


@dataclass(frozen=True)
class BackendEnvironmentSpec:
    """Registry-driven backend environment specification."""

    name: str
    packages: tuple[BackendEnvironmentPackage, ...]
    channels: tuple[str, ...]
    notes: tuple[str, ...]

    def package_names(self) -> tuple[str, ...]:
        """Return stable package identifiers in planned install order."""
        return tuple(package.name for package in self.packages)


def build_environment_spec(registry: BackendRegistry | None = None, channels: tuple[str, ...] = ("conda-forge", "pypi-placeholder")) -> BackendEnvironmentSpec:
    """Build the managed backend environment spec from the dependency registry."""
    registry_value = registry or default_backend_registry()
    dependencies = {dependency.name: dependency for dependency in registry_value.dependencies}
    packages = tuple(BackendEnvironmentPackage.from_dependency(dependencies[name]) for name in _REQUIRED_ENV_PACKAGES if name in dependencies)
    return BackendEnvironmentSpec(
        name="pyforestscan-backend",
        packages=packages,
        channels=channels,
        notes=(
            "Normal users see this as a preview; Phase 22C developer installs use this spec through staging.",
            "The backend environment is planned under the user-local PBM backend root, separate from QGIS Python.",
            "Exact version pins and lock files are deferred to Phase 22C after installer validation.",
        ),
    )
