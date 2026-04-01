#!/usr/bin/env python3
"""Download product images from JSON files to images/ID folders."""

import json
import os
from pathlib import Path
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

PRODUCTS_DIR = Path("products")
IMAGES_DIR = Path("images")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def download_image(url: str, dest_path: Path) -> bool:
    """Download a single image to dest_path. Returns True if successful."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(dest_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return False


def process_product(json_path: Path) -> dict:
    """Process a single product JSON file. Returns stats dict."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        images = data.get("product_information", {}).get("images", [])
        product_id = data.get("additional_information", {}).get("id")

        if not product_id or not images:
            return {"skipped": 1, "reason": "no id or images"}

        img_dir = IMAGES_DIR / product_id
        downloaded = 0
        skipped = 0

        # Check if already have enough images
        if img_dir.exists():
            existing_count = len([f for f in img_dir.iterdir() if f.is_file()])
            if existing_count >= len(images):
                return {"skipped": 1, "reason": f"already has {existing_count} images"}

        img_dir.mkdir(parents=True, exist_ok=True)

        for idx, url in enumerate(images):
            ext = url.rsplit(".", 1)[-1].split("?")[0]
            if not ext or len(ext) > 5:
                ext = "jpg"
            filename = f"{idx + 1}.{ext}"
            dest_path = img_dir / filename

            if dest_path.exists():
                skipped += 1
                continue

            if download_image(url, dest_path):
                downloaded += 1

        return {
            "product_id": product_id,
            "downloaded": downloaded,
            "skipped": skipped,
        }

    except Exception as e:
        return {"error": str(e), "path": str(json_path)}


def main():
    """Main entry point."""
    json_files = list(PRODUCTS_DIR.rglob("*.json"))
    total = len(json_files)
    print(f"Found {total} product JSON files")

    total_downloaded = 0
    total_skipped = 0
    errors = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_product, p): p for p in json_files}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            path = futures[future]

            if "error" in result:
                errors.append(result)
            elif "reason" in result:
                total_skipped += 1
            else:
                pid = result.get("product_id", "?")
                dl = result.get("downloaded", 0)
                sk = result.get("skipped", 0)
                total_downloaded += dl
                if dl > 0:
                    print(f"[{i}/{total}] {pid}: downloaded {dl}, skipped {sk}")

    print(f"\nDone! Downloaded {total_downloaded} images, skipped {total_skipped} products")
    if errors:
        print(f"Errors: {len(errors)}")

if __name__ == "__main__":
    main()