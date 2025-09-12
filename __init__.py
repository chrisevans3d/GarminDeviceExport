# -*- coding: utf-8 -*-
from .plugin import GeoResizerPlugin

def classFactory(iface):
    return GeoResizerPlugin(iface)
