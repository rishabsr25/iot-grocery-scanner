# IoT Grocery Scanner

Firmware for an ESP32-WROOM-32 paired with an Adafruit OV5640 camera module, designed to capture barcode images on a button press and stream them over WiFi for decoding. Built as the hardware sensing layer for a larger grocery price optimization project that pulls live pricing via the Kroger and Walmart APIs and calculates optimized shopping routes.

This repo currently includes the **Python barcode decoder** for low-resolution camera frames. ESP32 firmware will live here as the project grows.

## Barcode decoder

Decode 1D barcodes from low-resolution photos captured by the ESP32 + OV5640 rig. Built for **160x120 (QQVGA)** JPEG frames where breadboard wiring limits usable resolution.

### Setup (Windows)

```powershell
git clone https://github.com/rishabsr25/iot-grocery-scanner.git
cd iot-grocery-scanner
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`pyzbar` ships Windows wheels with bundled ZBar DLLs — no separate ZBar install required.

### Usage

```powershell
python decode_barcode.py path\to\your\barcode.jpg
```

Optional: save preprocessing variants for inspection:

```powershell
python decode_barcode.py path\to\your\barcode.jpg --save-debug debug_out
```

#### What the script tries

1. Original image (as-is)
2. Grayscale
3. Grayscale + autocontrast
4. Upscaled variants (2x, 4x, 6x) with LANCZOS resampling
5. Sharpening, contrast boost, and simple binary thresholds on upscaled images

The first stage that succeeds wins. Exit code `0` = barcode found, `2` = not found.

### pyzbar (ZBar) vs OpenCV barcode detector

| | **pyzbar / ZBar** | **OpenCV `BarcodeDetector`** |
|---|---|---|
| **Strength** | Mature 1D symbology support (UPC-A/E, EAN-13, Code128, etc.); fast; minimal deps | Integrated if you already use OpenCV; can leverage broader CV pipeline |
| **Low-res / blur** | Often better on noisy/blurred 1D barcodes when combined with upscaling + thresholding | Can struggle on heavily blurred or tiny barcodes without strong preprocessing |
| **Windows setup** | Pip wheel bundles DLLs | Requires `opencv-contrib-python` (heavier) |
| **This project** | **Primary choice** — tuned preprocessing pipeline for ZBar | Reasonable fallback if ZBar fails after aggressive preprocessing |

For ESP32 constraints (160x120, soft bar edges), **ZBar + upscaling/threshold preprocessing** is usually the better first approach.

## Hardware context

- ESP32-WROOM-32 (no PSRAM) + Adafruit OV5640
- Reliable capture at `FRAMESIZE_QQVGA` (160x120) only
- MJPEG stream at `http://<esp32-ip>:81/stream`

## Next phase (not implemented yet)

ESP32 button press → POST image to backend → decode → price lookup.

## License

MIT
