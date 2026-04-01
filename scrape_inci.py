#!/usr/bin/env python3
"""
Scrape INCI data from EU CosIng API.
Takes a search keyword as input.
Handles pagination and saves each page to a separate JSON file.
"""

import argparse
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any

# API Configuration
BASE_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "285a77fd-1257-4271-8507-f0c6b2961203"
OUTPUT_DIR = Path(__file__).parent / "inci_pages"
PAGE_SIZE = 100

# Request headers
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en,vi;q=0.9,to;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "No-Cache",
    "Connection": "keep-alive",
    "Origin": "https://ec.europa.eu",
    "Referer": "https://ec.europa.eu/"
}


def build_query(keyword: str) -> Dict[str, Any]:
    return {
        "bool": {
            "must": [
                {
                    "text": {
                        "query": keyword,
                        "fields": [
                            "inciName.exact",
                            "inciUsaName",
                            "innName.exact",
                            "phEurName",
                            "chemicalName",
                            "chemicalDescription"
                        ],
                        "defaultOperator": "AND"
                    }
                },
                {
                    "terms": {
                        "itemType": ["ingredient", "substance"]
                    }
                }
            ]
        }
    }


def fetch_page(keyword: str, page_number: int) -> Dict[str, Any]:
    """Fetch a single page of results from the API."""
    params = {
        "apiKey": API_KEY,
        "text": "*",
        "pageSize": PAGE_SIZE,
        "pageNumber": page_number
    }
    
    query_payload = build_query(keyword)
    files = {
        "query": ("blob", json.dumps(query_payload), "application/json")
    }

    try:
        response = requests.post(BASE_URL, params=params, headers=HEADERS, files=files, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching page {page_number}: {e}")
        return {}


def save_page(keyword: str, page_number: int, data: Dict[str, Any], output_dir: Path):
    """Save a single page to its own JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    safe_keyword = "".join([c if c.isalnum() else "_" for c in keyword])
    filename = output_dir / f"{safe_keyword}_page_{page_number:04d}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    results_count = len(data.get("results", []))
    print(f"  Saved page {page_number} ({results_count} results) to {filename}")


def scrape_all(keyword: str):
    """Scrape all pages and save each to a separate file."""
    print(f"Searching for: {keyword}")
    print("Fetching page 1 to determine total pages...")
    first_page = fetch_page(keyword, 1)

    if not first_page:
        print("Failed to fetch first page")
        return

    total_results = first_page.get("totalResults", 0)
    total_pages = (total_results + PAGE_SIZE - 1) // PAGE_SIZE
    
    safe_keyword = "".join([c if c.isalnum() else "_" for c in keyword])
    current_output_dir = OUTPUT_DIR / safe_keyword

    print(f"Total results: {total_results}")
    print(f"Total pages: {total_pages}")
    print(f"Page size: {PAGE_SIZE}")
    print(f"Output directory: {current_output_dir}")
    print()
    
    if total_results == 0:
        print("No results found.")
        return

    # Save first page
    save_page(keyword, 1, first_page, current_output_dir)

    # Fetch and save remaining pages
    for page in range(2, total_pages + 1):
        print(f"Fetching page {page}/{total_pages}...")
        data = fetch_page(keyword, page)
        if data:
            save_page(keyword, page, data, current_output_dir)

        # Rate limiting - be respectful to the API
        time.sleep(0.5)

    # Save metadata
    metadata = {
        "keyword": keyword,
        "total_results": total_results,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output_directory": str(current_output_dir)
    }
    metadata_file = current_output_dir / "_metadata.json"
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\nSaved metadata to {metadata_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape INCI data for a specific keyword.")
    parser.add_argument("keyword", help="The keyword to search for (e.g. 'aqua')")
    args = parser.parse_args()

    print("=" * 50)
    print("INCI Data Scraper")
    print("=" * 50)
    print()

    scrape_all(args.keyword)

    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)
