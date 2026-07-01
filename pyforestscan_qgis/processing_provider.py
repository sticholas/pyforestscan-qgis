"""Processing provider for PyForestScan QGIS."""

from __future__ import annotations

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithms.advanced import (
    AdvancedCanopyCoverAlgorithm,
    AdvancedChmAlgorithm,
    AdvancedDtmAlgorithm,
    AdvancedFhdAlgorithm,
    AdvancedPadAlgorithm,
    AdvancedPointDensityAlgorithm,
    AdvancedPaiAlgorithm,
    AdvancedRumpleAlgorithm,
    AdvancedVoxelStatAlgorithm,
    NormalizeHagAlgorithm,
    PointCloudPreprocessAlgorithm,
)
from .algorithms.placeholder_algorithms import EnvironmentCheckAlgorithm
from .resources import plugin_icon


class PyForestScanProvider(QgsProcessingProvider):
    """QGIS Processing provider exposing PyForestScan workflows."""

    PROVIDER_ID = "pyforestscan"
    PROVIDER_NAME = "PyForestScan"

    def id(self) -> str:
        """Return the stable Processing provider identifier."""
        return self.PROVIDER_ID

    def name(self) -> str:
        """Return the provider display name shown in QGIS."""
        return self.PROVIDER_NAME

    def longName(self) -> str:
        """Return the expanded provider name shown in Processing."""
        return self.PROVIDER_NAME

    def icon(self) -> QIcon:
        """Return the provider icon."""
        return plugin_icon()

    def loadAlgorithms(self) -> None:
        """Register all Processing algorithms owned by this provider."""
        self.addAlgorithm(EnvironmentCheckAlgorithm())
        self.addAlgorithm(AdvancedChmAlgorithm())
        self.addAlgorithm(AdvancedPadAlgorithm())
        self.addAlgorithm(AdvancedPaiAlgorithm())
        self.addAlgorithm(AdvancedCanopyCoverAlgorithm())
        self.addAlgorithm(AdvancedFhdAlgorithm())
        self.addAlgorithm(AdvancedRumpleAlgorithm())
        self.addAlgorithm(AdvancedPointDensityAlgorithm())
        self.addAlgorithm(AdvancedVoxelStatAlgorithm())
        self.addAlgorithm(NormalizeHagAlgorithm())
        self.addAlgorithm(AdvancedDtmAlgorithm())
        self.addAlgorithm(PointCloudPreprocessAlgorithm())

