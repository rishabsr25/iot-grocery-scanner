#!/usr/bin/env python3
"""Flask backend: identify products by perceptual hash against reference images."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import imagehash
from flask import Flask, jsonify, render_template_string, request
from PIL import Image

APP_DIR = Path(__file__).resolve().parent
REF_DIRS = (APP_DIR / "references", APP_DIR)

PRODUCTS: dict[str, dict] = {
    "gatorade": {
        "name": "Gatorade",
        "ref_file": "ref_gatorade.png",
        "prices": [
            {"store": "Kroger", "price": 1.29},
            {"store": "Local Market", "price": 1.49, "distance_miles": 2.1},
        ],
    },
    "lotion": {
        "name": "Lotion",
        "ref_file": "ref_lotion.png",
        "prices": [
            {"store": "Kroger", "price": 4.99},
            {"store": "Local Market", "price": 5.49, "distance_miles": 2.1},
        ],
    },
    "peanut_butter": {
        "name": "Peanut butter",
        "ref_file": "ref_peanutbutter.png",
        "prices": [
            {"store": "Kroger", "price": 3.49},
            {"store": "Local Market", "price": 3.89, "distance_miles": 2.1},
        ],
    },
}

app = Flask(__name__)
reference_hashes: dict[str, imagehash.ImageHash] = {}
last_identification: dict | None = None


@dataclass(frozen=True)
class MatchResult:
    product_id: str
    name: str
    hash_distance: int
    prices: list[dict]

    def to_json(self) -> dict:
        return {
            "product": self.name,
            "product_id": self.product_id,
            "hash_distance": self.hash_distance,
            "prices": self.prices,
        }


def resolve_ref_path(filename: str) -> Path:
    for directory in REF_DIRS:
        path = directory / filename
        if path.is_file():
            return path
    raise FileNotFoundError(f"Reference image not found: {filename}")


def load_reference_hashes() -> None:
    reference_hashes.clear()
    for product_id, product in PRODUCTS.items():
        path = resolve_ref_path(product["ref_file"])
        with Image.open(path) as image:
            reference_hashes[product_id] = imagehash.phash(image.convert("RGB"))


def identify_image(image: Image.Image) -> MatchResult:
    upload_hash = imagehash.phash(image.convert("RGB"))

    best_id = ""
    best_distance = float("inf")
    for product_id, ref_hash in reference_hashes.items():
        distance = upload_hash - ref_hash
        if distance < best_distance:
            best_distance = distance
            best_id = product_id

    product = PRODUCTS[best_id]
    return MatchResult(
        product_id=best_id,
        name=product["name"],
        hash_distance=int(best_distance),
        prices=product["prices"],
    )


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Grocery Scanner</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f6f7f9;
      --card: #ffffff;
      --text: #1a1a1a;
      --muted: #5c6670;
      --border: #d8dee4;
      --accent: #0b6bcb;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0f1419;
        --card: #1a2332;
        --text: #e8edf2;
        --muted: #9aa7b5;
        --border: #2a3644;
        --accent: #4da3ff;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    main {
      max-width: 720px;
      margin: 0 auto;
      padding: 2rem 1rem 3rem;
    }
    h1 { margin: 0 0 0.25rem; font-size: 1.75rem; }
    .subtitle { color: var(--muted); margin-bottom: 1.5rem; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .empty { color: var(--muted); }
    .product-name {
      font-size: 1.35rem;
      font-weight: 600;
      margin: 0 0 0.25rem;
    }
    .meta { color: var(--muted); font-size: 0.95rem; margin-bottom: 1rem; }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      text-align: left;
      padding: 0.65rem 0.5rem;
      border-bottom: 1px solid var(--border);
    }
    th { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }
    tr:last-child td { border-bottom: none; }
    .price { font-variant-numeric: tabular-nums; font-weight: 600; }
    .best { color: var(--accent); }
    code {
      background: var(--bg);
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <main>
    <h1>Grocery Scanner</h1>
    <p class="subtitle">Last product identified via <code>POST /identify</code></p>
    <div class="card">
      {% if last %}
        <p class="product-name">{{ last.product }}</p>
        <p class="meta">Hash distance: {{ last.hash_distance }}</p>
        <table>
          <thead>
            <tr>
              <th>Store</th>
              <th>Price</th>
              <th>Distance</th>
            </tr>
          </thead>
          <tbody>
            {% for row in last.prices %}
            <tr>
              <td>{{ row.store }}</td>
              <td class="price">${{ "%.2f"|format(row.price) }}</td>
              <td>{% if row.distance_miles is defined %}{{ row.distance_miles }} mi{% else %}—{% endif %}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <p class="empty">No product identified yet. POST an image to <code>/identify</code>.</p>
      {% endif %}
    </div>
  </main>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(INDEX_HTML, last=last_identification)


@app.route("/identify", methods=["POST"])
def identify():
    global last_identification

    if "image" not in request.files:
        return jsonify({"error": "Missing image file. Use form field 'image'."}), 400

    upload = request.files["image"]
    if not upload.filename:
        return jsonify({"error": "Empty filename."}), 400

    try:
        raw = upload.read()
        with Image.open(io.BytesIO(raw)) as image:
            result = identify_image(image)
    except Exception as exc:
        return jsonify({"error": f"Could not read image: {exc}"}), 400

    payload = result.to_json()
    last_identification = payload
    return jsonify(payload)


load_reference_hashes()


if __name__ == "__main__":
    print("Loaded reference hashes:", ", ".join(reference_hashes))
    app.run(host="0.0.0.0", port=5000, debug=True)
