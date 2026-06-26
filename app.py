#!/usr/bin/env python3
"""Flask backend: identify products via Google Gemini vision API."""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request
from google import genai
from google.genai import types


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_PROMPT = (
    "You are looking at a blurry low-resolution camera image. The image contains exactly one of "
    "these three products: (1) a blue/teal Gatorade sports drink bottle, (2) a tall brown lotion "
    "bottle with a dark pump cap, (3) a short wide peanut butter jar with a green lid. Look at the "
    "dominant colors and shape in the image and pick the closest match. Reply with ONLY one word: "
    "gatorade, lotion, or peanutbutter. Do not say anything else."
)

PRODUCTS: dict[str, dict] = {
    "gatorade": {
        "name": "Gatorade",
        "prices": [
            {"store": "Kroger", "price": 1.29},
            {"store": "Local Market", "price": 1.49, "distance_miles": 2.1},
        ],
    },
    "lotion": {
        "name": "Lotion",
        "prices": [
            {"store": "Kroger", "price": 4.99},
            {"store": "Local Market", "price": 5.49, "distance_miles": 2.1},
        ],
    },
    "peanut_butter": {
        "name": "Peanut butter",
        "prices": [
            {"store": "Kroger", "price": 3.49},
            {"store": "Local Market", "price": 3.89, "distance_miles": 2.1},
        ],
    },
}

app = Flask(__name__)
last_identification: dict | None = None
scan_history: deque[dict] = deque(maxlen=5)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


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


def record_scan(payload: dict) -> None:
    entry = {
        **payload,
        "scanned_at": datetime.now(UTC).isoformat(),
    }
    scan_history.appendleft(entry)


def detect_mime_type(raw: bytes) -> str:
    if raw.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a"):
        return "image/gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def parse_gemini_product_id(text: str | None) -> str:
    if not text:
        raise ValueError("Empty response from Gemini")

    normalized = text.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    aliases = {
        "gatorade": "gatorade",
        "lotion": "lotion",
        "peanutbutter": "peanut_butter",
    }
    if normalized in aliases:
        return aliases[normalized]

    raise ValueError(f"Unrecognized product from Gemini: {text!r}")


def identify_image(raw: bytes, mime_type: str) -> MatchResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            GEMINI_PROMPT,
            types.Part.from_bytes(data=raw, mime_type=mime_type),
        ],
    )

    product_id = parse_gemini_product_id(response.text)
    product = PRODUCTS[product_id]
    return MatchResult(
        product_id=product_id,
        name=product["name"],
        hash_distance=0,
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
        if not raw:
            return jsonify({"error": "Empty image file."}), 400
        mime_type = detect_mime_type(raw)
        result = identify_image(raw, mime_type)
    except Exception as exc:
        return jsonify({"error": f"Could not identify image: {exc}"}), 400

    payload = result.to_json()
    last_identification = payload
    record_scan(payload)
    return jsonify(payload)


@app.route("/history")
def history():
    return jsonify({"history": list(scan_history)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
