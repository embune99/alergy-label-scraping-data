#!/usr/bin/env python3
"""
Scrape INCI data from EU CosIng API.
Handles pagination and saves each page to a separate JSON file.
"""

import json
import time
import requests
from pathlib import Path
from typing import Dict, Any


# API Configuration
BASE_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "285a77fd-1257-4271-8507-f0c6b2961203"
OUTPUT_DIR = Path(__file__).parent / "inci_pages"
PAGE_SIZE = 200
SEARCH_TERM = "*"

# Request headers
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Cache-Control": "No-Cache",
    "Connection": "keep-alive",
    "Origin": "https://ec.europa.eu",
    "Referer": "https://ec.europa.eu/"
}


def fetch_page(page_number: int) -> Dict[str, Any]:
    """Fetch a single page of results from the API."""
    params = {
        "apiKey": API_KEY,
        "text": SEARCH_TERM,
        "pageSize": PAGE_SIZE,
        "pageNumber": page_number
    }

    try:
        response = requests.post(BASE_URL, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching page {page_number}: {e}")
        return {}


def save_page(page_number: int, data: Dict[str, Any], output_dir: Path):
    """Save a single page to its own JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"page_{page_number:04d}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    results_count = len(data.get("results", []))
    print(f"  Saved page {page_number} ({results_count} results) to {filename}")


def scrape_all():
    """Scrape all pages and save each to a separate file."""
    # First, fetch page 1 to get total results count
    print("Fetching page 1 to determine total pages...")
    first_page = fetch_page(1)

    if not first_page:
        print("Failed to fetch first page")
        return

    total_results = first_page.get("totalResults", 0)
    total_pages = (total_results + PAGE_SIZE - 1) // PAGE_SIZE

    print(f"Total results: {total_results}")
    print(f"Total pages: {total_pages}")
    print(f"Page size: {PAGE_SIZE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Save first page
    save_page(1, first_page, OUTPUT_DIR)

    # Fetch and save remaining pages
    for page in range(2, total_pages + 1):
        print(f"Fetching page {page}/{total_pages}...")
        data = fetch_page(page)
        if data:
            save_page(page, data, OUTPUT_DIR)

        # Rate limiting - be respectful to the API
        time.sleep(0.5)

    # Save metadata
    metadata = {
        "total_results": total_results,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output_directory": str(OUTPUT_DIR)
    }
    metadata_file = OUTPUT_DIR / "_metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\nSaved metadata to {metadata_file}")


if __name__ == "__main__":
    print("=" * 50)
    print("INCI Data Scraper")
    print("=" * 50)
    print()

    scrape_all()

    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)
