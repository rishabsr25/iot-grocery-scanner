#!/usr/bin/env python3
"""Decode 1D barcodes from low-resolution ESP32 camera images using pyzbar/ZBar."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pyzbar.pyzbar import decode as zbar_decode


@dataclass(frozen=True)
class DecodeResult:
    stage: str
    symbology: str
    data: str


def decode_image(image: Image.Image) -> list[DecodeResult]:
    """Run ZBar on a PIL image and return unique decoded symbols."""
    seen: set[tuple[str, str]] = set()
    results: list[DecodeResult] = []

    for symbol in zbar_decode(image):
        symbology = symbol.type or "UNKNOWN"
        payload = symbol.data.decode("utf-8", errors="replace")
        key = (symbology, payload)
        if key in seen:
            continue
        seen.add(key)
        results.append(DecodeResult(stage="", symbology=symbology, data=payload))

    return results


def upscale(image: Image.Image, factor: float) -> Image.Image:
    width, height = image.size
    return image.resize(
        (max(1, int(width * factor)), max(1, int(height * factor))),
        Image.Resampling.LANCZOS,
    )


def build_variants(image: Image.Image) -> list[tuple[str, Image.Image]]:
    """Generate progressively stronger preprocessing variants."""
    gray = image.convert("L")
    variants: list[tuple[str, Image.Image]] = [
        ("original", image),
        ("grayscale", gray),
        ("grayscale + autocontrast", ImageOps.autocontrast(gray)),
        ("grayscale + autocontrast + 2x upscale", upscale(ImageOps.autocontrast(gray), 2.0)),
        ("grayscale + autocontrast + 4x upscale", upscale(ImageOps.autocontrast(gray), 4.0)),
        ("grayscale + autocontrast + 6x upscale", upscale(ImageOps.autocontrast(gray), 6.0)),
        (
            "grayscale + autocontrast + sharpen + 4x upscale",
            upscale(ImageOps.autocontrast(gray).filter(ImageFilter.SHARPEN), 4.0),
        ),
        (
            "grayscale + autocontrast + contrast boost + 4x upscale",
            upscale(ImageEnhance.Contrast(ImageOps.autocontrast(gray)).enhance(1.8), 4.0),
        ),
        (
            "binary threshold (128) + 4x upscale",
            upscale(gray.point(lambda px: 255 if px > 128 else 0, mode="1").convert("L"), 4.0),
        ),
        (
            "binary threshold (Otsu-ish 96) + 4x upscale",
            upscale(gray.point(lambda px: 255 if px > 96 else 0, mode="1").convert("L"), 4.0),
        ),
    ]
    return variants


def try_decode_all_stages(image: Image.Image) -> list[DecodeResult]:
    hits: list[DecodeResult] = []
    seen: set[tuple[str, str]] = set()

    for stage_name, variant in build_variants(image):
        for result in decode_image(variant):
            key = (result.symbology, result.data)
            if key in seen:
                continue
            seen.add(key)
            hits.append(DecodeResult(stage=stage_name, symbology=result.symbology, data=result.data))

        if hits:
            return hits

    return hits


def print_results(image_path: Path, results: list[DecodeResult]) -> None:
    print(f"Image: {image_path.resolve()}")

    if not results:
        print("\nNo barcode found.")
        print(
            "\nIf all stages failed, the image may be too blurred or the barcode too small "
            "at 160x120. Try cropping tightly to the barcode, improving lighting, or moving "
            "closer so the bars occupy more of the frame."
        )
        return

    print(f"\nBarcode found ({len(results)} unique result(s)):\n")
    for index, result in enumerate(results, start=1):
        print(f"  [{index}] Stage: {result.stage}")
        print(f"      Type:  {result.symbology}")
        print(f"      Data:  {result.data}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode 1D barcodes from ESP32/OV5640 camera images using pyzbar."
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Path to the barcode image (JPEG/PNG/etc.)",
    )
    parser.add_argument(
        "--save-debug",
        type=Path,
        default=None,
        help="Optional directory to write preprocessing variants for inspection",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    image_path: Path = args.image

    if not image_path.is_file():
        print(f"Error: file not found: {image_path}", file=sys.stderr)
        return 1

    image = Image.open(image_path)
    print(f"Loaded {image_path.name}: {image.size[0]}x{image.size[1]} {image.mode}")

    if args.save_debug:
        args.save_debug.mkdir(parents=True, exist_ok=True)
        for stage_name, variant in build_variants(image):
            safe_name = stage_name.lower().replace(" ", "_").replace("+", "plus").replace("(", "").replace(")", "")
            variant.save(args.save_debug / f"{safe_name}.png")

    results = try_decode_all_stages(image)
    print_results(image_path, results)
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
