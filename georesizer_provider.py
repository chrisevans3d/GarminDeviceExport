# -*- coding: utf-8 -*-
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon
from .algorithms.export_kmz import ExportKMZAlgorithm

class GeoResizerProvider(QgsProcessingProvider):
    def id(self):
        return 'GarminDeviceExport'

    def name(self):
        return 'GarminDeviceExport'

    def longName(self):
        return 'GarminDeviceExport'

    def shortName(self):
        return 'GarminDeviceExport'

    def icon(self):
        return QIcon()

    def loadAlgorithms(self):
        self.addAlgorithm(ExportKMZAlgorithm())
