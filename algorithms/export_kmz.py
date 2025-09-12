# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterFileDestination,
    QgsProcessingParameterEnum, QgsProcessingParameterNumber,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject,
)
from osgeo import gdal
from PIL import Image
import numpy as np
import zipfile, io, math

# Per-tile constraints
MAX_PIXELS  = 1_000_000     # ≤1 MP
MAX_BYTES   = 3 * 1024 * 1024  # ≤3 MB
JPEG_QUALITY = 75           # non-progressive baseline
TILE_SIDE   = int(math.ceil(math.sqrt(MAX_PIXELS)))  # ~1000 px

DEVICES = ['eTrex (≤100 tiles)', 'GPSMAP (≤500 tiles)', 'Custom']
DEVICE_LIMITS = [100, 500]

HELP_NOTE = (
    "This exports tiles capped at the Garmin published limits:\n"
    "  • eTrex, Monterra – up to ~100 tiles\n"
    "  • GPSMAP, Montana, Oregon – up to ~500 tiles\n"
    "Selecting eTrex or GPSMAP will generate the highest quality possible within the tile cap. "
    "Choose 'Custom' to enter your own maximum tile count. Each tile is ≤1MP and ≤3MB, JPEG (non‑progressive, q=75)."
)

class ExportKMZAlgorithm(QgsProcessingAlgorithm):
    INPUT      = 'INPUT'
    OUTPUT     = 'OUTPUT'
    DEVICE     = 'DEVICE'       # enum eTrex/GPSMAP/Custom
    CUSTOM_CAP = 'CUSTOM_CAP'   # integer when Custom

    def tr(self, text): return QCoreApplication.translate('Processing', text)
    def createInstance(self): return ExportKMZAlgorithm()
    def name(self): return 'export_kmz'
    def displayName(self): return self.tr('Export Garmin KMZ')
    def group(self): return 'Garmin Custom Map Resize and Export'
    def groupId(self): return 'georesizer'
    def shortHelpString(self): return HELP_NOTE

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr('Raster layer')))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr('Output KMZ'), 'KMZ (*.kmz)'))
        self.addParameter(QgsProcessingParameterEnum(self.DEVICE, self.tr('Target device'), options=DEVICES, defaultValue=0))

        p = QgsProcessingParameterNumber(
            self.CUSTOM_CAP,
            self.tr('Custom tile cap (used only when device=Custom)'),
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=250,
            minValue=1
        )
        try:
            p.setMetadata({'widget_wrapper': {'suffix': '  (Tiles)'}})
        except Exception:
            pass
        self.addParameter(p)

    def processAlgorithm(self, parameters, context, feedback):
        layer    = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        out_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        dev_ix   = int(self.parameterAsEnum(parameters, self.DEVICE, context))
        custom   = int(self.parameterAsInt(parameters, self.CUSTOM_CAP, context))

        if dev_ix == 2:  # Custom
            tile_cap = max(1, custom)
        else:
            tile_cap = DEVICE_LIMITS[max(0, min(dev_ix, len(DEVICE_LIMITS)-1))]

        provider = layer.dataProvider()
        src_path = provider.dataSourceUri().split('|')[0]

        W, H = layer.width(), layer.height()
        s = self._scale_for_tile_cap(W, H, TILE_SIDE, tile_cap)
        newW, newH = max(1, int(round(W*s))), max(1, int(round(H*s)))

        cols = int(math.ceil(newW / float(TILE_SIDE)))
        rows = int(math.ceil(newH / float(TILE_SIDE)))
        tiles = cols * rows

        device_name = DEVICES[dev_ix] if 0 <= dev_ix < len(DEVICES) else 'Custom'
        feedback.pushInfo(f"Device: {device_name}; Tile cap: {tile_cap}. "
                          f"Original: {W}×{H} px → Resampled: {newW}×{newH} px. "
                          f"Tiling grid: {cols}×{rows} = {tiles} tiles.")

        # Render resampled raster to memory
        ds = gdal.Translate('', src_path, options=gdal.TranslateOptions(
            width=newW, height=newH, resampleAlg='average', format='MEM'
        ))

        try:
            arr = ds.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize)
            bands = ds.RasterCount
            if bands == 1:
                a = arr.astype('float32')
                mn, mx = float(a.min()), float(a.max())
                a = np.zeros_like(a) if mx <= mn else (a - mn) * (255.0 / (mx - mn))
                rgb = np.stack([a, a, a]).astype('uint8')
            else:
                rgb = arr[:3] if arr.ndim == 3 else arr
                if rgb.dtype != np.uint8:
                    rgb = rgb.astype('float32')
                    for i in range(rgb.shape[0]):
                        mn, mx = float(rgb[i].min()), float(rgb[i].max())
                        rgb[i] = 0 if mx <= mn else (rgb[i] - mn) * (255.0 / (mx - mn))
                    rgb = rgb.astype('uint8')

            from PIL import Image
            base_img = Image.fromarray(rgb.transpose(1, 2, 0))

            # WGS84 extents
            extent = layer.extent()
            wgs84  = QgsCoordinateReferenceSystem('EPSG:4326')
            ct     = QgsCoordinateTransform(layer.crs(), wgs84, QgsProject.instance())
            rect   = ct.transformBoundingBox(extent)
            north0, south0, east0, west0 = rect.yMaximum(), rect.yMinimum(), rect.xMaximum(), rect.xMinimum()
            lon_span, lat_span = east0 - west0, north0 - south0

            tile_w = int(math.ceil(base_img.width / float(cols)))
            tile_h = int(math.ceil(base_img.height / float(rows)))

            overlays = []  # (fname, bytes, west, east, south, north)

            def jpg75_nonprog(img):
                buf = io.BytesIO()
                img.convert('RGB').save(buf, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=False)
                return buf.getvalue()

            idx = 0
            for r in range(rows):
                for c in range(cols):
                    x0, y0 = c*tile_w, r*tile_h
                    x1, y1 = min(base_img.width, x0+tile_w), min(base_img.height, y0+tile_h)
                    if x0 >= x1 or y0 >= y1:
                        idx += 1; continue

                    tile = base_img.crop((x0, y0, x1, y1))

                    # Enforce 1MP per tile
                    tw, th = tile.size
                    scale_mp = min(1.0, math.sqrt(MAX_PIXELS / float(max(1, tw*th))))
                    if scale_mp < 1.0:
                        tile = tile.resize((max(1,int(tw*scale_mp)), max(1,int(th*scale_mp))), Image.LANCZOS)

                    jpg = jpg75_nonprog(tile)
                    while len(jpg) > MAX_BYTES and (tile.width*tile.height) > 64*64:
                        tile = tile.resize((max(1,int(tile.width*0.9)), max(1,int(tile.height*0.9))), Image.LANCZOS)
                        jpg = jpg75_nonprog(tile)

                    # width/height in degrees
                    lon_span = east0 - west0
                    lat_span = north0 - south0

                    twest = west0 + lon_span * (x0 / float(base_img.width))
                    teast = west0 + lon_span * (x1 / float(base_img.width))
                    tnorth = north0 - lat_span * (y0 / float(base_img.height))  # flip Y
                    tsouth = north0 - lat_span * (y1 / float(base_img.height))  # flip Y

                    overlays.append((f"image_{idx:03d}.jpg", jpg, twest, teast, tsouth, tnorth))
                    idx += 1

            # Build KML
            layer_name = layer.name()
            parts = [
                "<?xml version='1.0' encoding='UTF-8'?>",
                "<kml xmlns='http://www.opengis.net/kml/2.2'>",
                "  <Document>",
                f"    <name>{layer_name}</name>",
                f"    <description>QGIS GarminDeviceExport by Chris.Evans@gmail.com – {tiles} tiles</description>"

            ]
            for fname, data, w, e, s, n in overlays:
                parts += [
                    "    <GroundOverlay>",
                    "      <Icon>",
                    f"        <href>{fname}</href>",
                    "      </Icon>",
                    "      <LatLonBox>",
                    f"        <north>{n}</north>",
                    f"        <south>{s}</south>",
                    f"        <east>{e}</east>",
                    f"        <west>{w}</west>",
                    "      </LatLonBox>",
                    "    </GroundOverlay>",
                ]
            parts += ["  </Document>", "</kml>"]
            kml = "\n".join(parts)

            with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                z.writestr('doc.kml', kml)
                for fname, data, *_ in overlays:
                    z.writestr(fname, data)

            return { self.OUTPUT: out_path }

        finally:
            ds = None

    @staticmethod
    def _scale_for_tile_cap(W, H, tile_side, cap):
        # Largest s in (0,1] so that ceil(W*s/t)*ceil(H*s/t) <= cap
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2.0
            cols = int(math.ceil((W * mid) / float(tile_side)))
            rows = int(math.ceil((H * mid) / float(tile_side)))
            if max(1, cols) * max(1, rows) <= cap:
                lo = mid
            else:
                hi = mid
        return max(1e-6, lo)
