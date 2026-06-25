"""Project-level adapter state for PyForestScan QGIS."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import AdapterConfig
from .types import DatasetSource


@dataclass(frozen=True)
class PyForestScanProject:
    """Immutable project context owned by the QGIS plugin, not PyForestScan."""

    name: str
    root: Path | None = None
    config: AdapterConfig = field(default_factory=AdapterConfig)
    datasets: tuple[DatasetSource, ...] = ()

    def with_dataset(self, dataset: DatasetSource) -> "PyForestScanProject":
        """Return a new project context with an additional dataset reference."""
        return PyForestScanProject(
            name=self.name,
            root=self.root,
            config=self.config,
            datasets=self.datasets + (dataset,),
        )
