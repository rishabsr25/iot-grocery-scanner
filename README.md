# ESP32 Barcode Decoder

Decode 1D barcodes from low-resolution photos captured by an ESP32 + OV5640 camera rig. Built for **160x120 (QQVGA)** JPEG frames where breadboard wiring limits usable resolution.

## Setup (Windows)

```powershell
cd C:\Users\risha\Projects\esp32-barcode-decoder
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`pyzbar` ships Windows wheels with bundled ZBar DLLs — no separate ZBar install required.

## Usage

```powershell
python decode_barcode.py path\to\your\barcode.jpg
```

Optional: save preprocessing variants for inspection:

```powershell
python decode_barcode.py path\to\your\barcode.jpg --save-debug debug_out
```

### What the script tries

1. Original image (as-is)
2. Grayscale
3. Grayscale + autocontrast
4. Upscaled variants (2x, 4x, 6x) with LANCZOS resampling
5. Sharpening, contrast boost, and simple binary thresholds on upscaled images

The first stage that succeeds wins. Exit code `0` = barcode found, `2` = not found.

## pyzbar (ZBar) vs OpenCV barcode detector

| | **pyzbar / ZBar** | **OpenCV `BarcodeDetector`** |
|---|---|---|
| **Strength** | Mature 1D symbology support (UPC-A/E, EAN-13, Code128, etc.); fast; minimal deps | Integrated if you already use OpenCV; can leverage broader CV pipeline |
| **Low-res / blur** | Often better on noisy/blurred 1D barcodes when combined with upscaling + thresholding | Can struggle on heavily blurred or tiny barcodes without strong preprocessing |
| **Windows setup** | Pip wheel bundles DLLs | Requires `opencv-contrib-python` (heavier) |
| **This project** | **Primary choice** — tuned preprocessing pipeline for ZBar | Reasonable fallback if ZBar fails after aggressive preprocessing |

For your ESP32 constraints (160x120, soft bar edges), **ZBar + upscaling/threshold preprocessing** is usually the better first approach.

## Hardware context

- ESP32-WROOM-32 (no PSRAM) + Adafruit OV5640
- Reliable capture at `FRAMESIZE_QQVGA` (160x120) only
- MJPEG stream at `http://<esp32-ip>:81/stream`

## Next phase (not implemented yet)

ESP32 button press → POST image to backend → decode → price lookup.

## License

MIT
