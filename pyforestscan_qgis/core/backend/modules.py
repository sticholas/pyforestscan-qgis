"""Future backend module registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import BackendDependency


class BackendModule(Protocol):
    """Protocol for future PBM backend modules."""

    name: str
    display_name: str

    def dependencies(self) -> tuple[BackendDependency, ...]:
        """Return module dependencies."""

    def verification_steps(self) -> tuple[str, ...]:
        """Return module verification steps."""

    def repair_steps(self) -> tuple[str, ...]:
        """Return module repair steps."""

    def update_steps(self) -> tuple[str, ...]:
        """Return module update steps."""


@dataclass(frozen=True)
class DeclarativeBackendModule:
    """Declarative module placeholder for future optional stacks."""

    name: str
    display_name: str
    dependency_names: tuple[str, ...]
    install_routine: str
    verification: tuple[str, ...]
    repair: tuple[str, ...]
    update: tuple[str, ...]

    def dependencies(self) -> tuple[BackendDependency, ...]:
        """Return placeholder dependencies for this module."""
        return tuple(
            BackendDependency(
                name=name,
                display_name=name,
                category=f"module:{self.name}",
                required=False,
                version_spec="future",
                source="future module registry",
                notes=f"Owned by future {self.display_name} module.",
            )
            for name in self.dependency_names
        )

    def verification_steps(self) -> tuple[str, ...]:
        """Return declarative verification steps."""
        return self.verification

    def repair_steps(self) -> tuple[str, ...]:
        """Return declarative repair steps."""
        return self.repair

    def update_steps(self) -> tuple[str, ...]:
        """Return declarative update steps."""
        return self.update


@dataclass
class BackendModuleRegistry:
    """Registry for PBM backend modules."""

    modules: dict[str, BackendModule]

    def register(self, module: BackendModule) -> None:
        """Register or replace a backend module."""
        self.modules[module.name] = module

    def names(self) -> tuple[str, ...]:
        """Return registered module names."""
        return tuple(sorted(self.modules))

    def get(self, name: str) -> BackendModule | None:
        """Return one module by name."""
        return self.modules.get(name)


def default_backend_module_registry() -> BackendModuleRegistry:
    """Return declarative placeholders for future module architecture."""
    registry = BackendModuleRegistry(modules={})
    for module in (
        DeclarativeBackendModule("pdal", "PDAL Module", ("pdal", "python-pdal"), "manifest environment", ("pdal --version", "import pdal"), ("recreate environment",), ("manifest upgrade",)),
        DeclarativeBackendModule("pytorch", "PyTorch Module", ("pytorch",), "future optional module", ("import torch",), ("repair optional package",), ("module upgrade",)),
        DeclarativeBackendModule("sam", "SAM Module", ("segment-anything", "onnx-runtime"), "future optional module", ("import segment_anything",), ("repair model dependencies",), ("module upgrade",)),
        DeclarativeBackendModule("whiteboxtools", "WhiteboxTools Module", ("whiteboxtools",), "future optional module", ("whitebox_tools --version",), ("restore executable",), ("module upgrade",)),
        DeclarativeBackendModule("cloudcompare", "CloudCompare Module", ("cloudcompare-cli",), "future optional module", ("CloudCompare --version",), ("restore executable",), ("module upgrade",)),
        DeclarativeBackendModule("potree", "Potree Module", ("potree-converter",), "future optional module", ("PotreeConverter --version",), ("restore executable",), ("module upgrade",)),
    ):
        registry.register(module)
    return registry
