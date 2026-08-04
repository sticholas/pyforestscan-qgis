"""Explicit retained-interface event hub."""
from qgis.PyQt.QtCore import QObject, pyqtSignal

class SessionStateEvents(QObject):
    repositoryChanged = pyqtSignal(object)
    repositoryStatusChanged = pyqtSignal(object)
    polygonSelectionChanged = pyqtSignal(object)
    polygonGeometryChanged = pyqtSignal(object)
    productsChanged = pyqtSignal(object)
    outputFolderChanged = pyqtSignal(object)
    executionPlanChanged = pyqtSignal(object)
    backendStatusChanged = pyqtSignal(object)
    environmentStatusChanged = pyqtSignal(object)
    processingStarted = pyqtSignal(object)
    processingProgressChanged = pyqtSignal(object)
    processingCompleted = pyqtSignal(object)
    processingFailed = pyqtSignal(object)
    outputsRegistered = pyqtSignal(object)
    outputsLoaded = pyqtSignal(object)
    sessionReset = pyqtSignal(object)
