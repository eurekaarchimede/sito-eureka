#!/usr/bin/env python3
"""Generate small JPEG copies for the mobile site, preserving originals.

Requires Pillow, already available in the local workspace runtime.
Run from any directory: python3 scripts/optimize-images.py

Stable output paths:
  foto/name.jpg -> assets/optimized/foto/name.jpg
  assets/ig/id.jpg -> assets/optimized/ig/id.jpg
Only Instagram images referenced by the local feed are processed.
assets/optimized/manifest.json maps originals to copies and their dimensions.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "optimized"
MANIFEST = OUTPUT / "manifest.json"
FEED = ROOT / "assets" / "ig" / "feed.json"
QUALITY = 78


def sources():
    """Yield unique, local inputs with the maximum output width."""
    for path in sorted((ROOT / "foto").glob("*.jpg")):
        yield path, OUTPUT / "foto" / path.name, 600

    feed = json.loads(FEED.read_text(encoding="utf-8"))
    seen = set()
    for post in feed.get("posts", []):
        reference = post.get("image")
        if not isinstance(reference, str):
            continue
        path = (ROOT / reference).resolve()
        # Never download remote images or process a feed path outside assets/ig.
        if path.parent != (ROOT / "assets" / "ig").resolve():
            continue
        if path in seen or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        seen.add(path)
        yield path, OUTPUT / "ig" / f"{path.stem}.jpg", 720


def optimize(source, destination, max_width):
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)
        if image.mode != "RGB":
            image = image.convert("RGB")
        if image.width > max_width:
            height = max(1, round(image.height * max_width / image.width))
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Replace only a complete JPEG, so an interrupted run preserves the previous copy.
        temporary = destination.with_suffix(".jpg.tmp")
        image.save(temporary, format="JPEG", quality=QUALITY, optimize=True, progressive=True)
        temporary.replace(destination)
        return image.size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="regenerate existing copies")
    args = parser.parse_args()
    totals = {"foto": [0, 0, 0], "ig": [0, 0, 0]}
    manifest = {}
    generated = 0
    for source, destination, max_width in sources():
        if not source.is_file():
            raise FileNotFoundError(f"Referenced source image is missing: {source}")
        if (args.force or not destination.exists()
                or destination.stat().st_mtime < source.stat().st_mtime):
            optimize(source, destination, max_width)
            generated += 1
        with Image.open(destination) as image:
            manifest[source.relative_to(ROOT).as_posix()] = {
                "src": destination.relative_to(ROOT).as_posix(),
                "width": image.width,
                "height": image.height,
            }
        bucket = totals[destination.parent.name]
        bucket[0] += 1
        bucket[1] += source.stat().st_size
        bucket[2] += destination.stat().st_size
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(MANIFEST)
    for group, (count, original, optimized) in totals.items():
        saved = (1 - optimized / original) * 100 if original else 0
        print(f"{group}: {count} images, {original:,} -> {optimized:,} bytes ({saved:.1f}% saved)")
    print(f"Generated {generated} optimized copies; originals preserved.")


if __name__ == "__main__":
    main()
