# -*- coding: utf-8 -*-
from qgis.core import QgsApplication
from .georesizer_provider import GeoResizerProvider

class GeoResizerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        self.provider = GeoResizerProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
