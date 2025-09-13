# GeoResizer QGIS Plugin

**GeoResizer** is a QGIS Processing plugin that exports any raster layer to a **Google Earth KMZ** with tiling optimized for Garmin GPS devices.  

Each tile is:
- JPEG @ quality **75** (non-progressive, baseline)
- ≤ **1 megapixel** in resolution
- ≤ **3 MB** in size

The plugin automatically resamples and tiles your raster so that the total number of tiles does not exceed the limit for the selected device.

---

## Features

- **Device-aware tiling**  
  Choose a target device:
  - **eTrex** (≤100 tiles)
  - **GPSMAP** (≤500 tiles)
  - **Custom** (enter your own maximum tile count)

- **Resampling to fit device limits**  
  If your raster is very large, GeoResizer automatically downsamples to ensure the generated KMZ stays within the device’s tile cap.

- **KML metadata**  
  - The `<name>` in the KML is set to the QGIS raster layer’s name.  
  - The `<description>` includes attribution:  
    ```
    QGIS GarminDeviceExport by Chris.Evans@gmail.com – N tiles
    ```
    where `N` is the number of tiles in the KMZ.

- **Baseline JPEG compression**  
  Files are non-progressive JPEGs at quality 75 for maximum compatibility with Garmin and Google Earth.

---

## Installation

1. Download the latest release ZIP from [Releases](./releases).
2. In QGIS, go to **Plugins → Manage and Install Plugins… → Install from ZIP**.
3. Select the downloaded ZIP.  
   This will install the plugin into your QGIS profile’s `python/plugins/` directory.

---

## Usage

1. Open the **Processing Toolbox** in QGIS (`Processing → Toolbox`).
2. Find **GeoResizer → Export KMZ (device-aware tiling, JPEG@75 non-progressive)**.
3. Parameters:
   - **Raster layer**: The input raster to export.
   - **Output KMZ**: Path to the generated KMZ file.
   - **Target device**: eTrex, GPSMAP, or Custom.
   - **Custom tile cap**: Only used when **Custom** is selected.
4. Run the algorithm.  
   A KMZ file will be created with one GroundOverlay per tile.

---

## Notes

- Works with QGIS 3.16+ and GDAL ≥ 3.
- Each tile is auto-downscaled if it would exceed 1 MP or 3 MB at q=75.
- KMZ opens directly in Google Earth; Garmin devices accept KMZ overlays through their Custom Maps feature.

---

## License

MIT License © 2025 Chris Evans

⚠️ Note: Parts of this plugin were generated with the assistance of a Large Language Model (LLM).  
The code was reviewed, adapted, and tested by the project maintainer.

