#!/usr/bin/env python3
"""
Scrape INCI data from EU CosIng API.
Takes a search keyword as input.
Handles pagination and saves each page to a separate JSON file.
"""

import argparse
import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, Any

# API Configuration
BASE_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "285a77fd-1257-4271-8507-f0c6b2961203"
OUTPUT_DIR = Path(__file__).parent / "inci_pages"
CACHE_DIR = Path(__file__).parent / "cache"
PAGE_SIZE = 100

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)

# Request headers
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en,vi;q=0.9,to;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "No-Cache",
    "Connection": "keep-alive",
    "Origin": "https://ec.europa.eu",
    "Referer": "https://ec.europa.eu/"
}


def sanitize_filename(keyword: str) -> str:
    """Sanitize keyword to be used as a filename."""
    # Replace invalid filename characters with underscore
    # Keep only alphanumeric, hyphen, underscore, and space
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', keyword)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


def get_cache_path(keyword: str) -> Path:
    """Get the cache file path for a keyword."""
    filename = sanitize_filename(keyword) + ".json"
    return CACHE_DIR / filename


def load_from_cache(keyword: str) -> Dict[str, Any] | None:
    """Load cached response for a keyword if available."""
    cache_path = get_cache_path(keyword)
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cache for '{keyword}': {e}")
    return None


def save_to_cache(keyword: str, data: Dict[str, Any]) -> None:
    """Save API response to cache."""
    cache_path = get_cache_path(keyword)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing cache for '{keyword}': {e}")


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


def fetch_page(keyword: str, page_number: int, use_cache: bool = True) -> Dict[str, Any] | None:
    """Fetch a single page of results from the API and return the best matching item."""
    # Check cache first
    if use_cache and page_number == 1:
        cached_result = load_from_cache(keyword)
        if cached_result is not None:
            print(f"  [Cache hit for '{keyword}']")
            return cached_result

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
        results = response.json().get("results", [])

        if not results:
            # API returned 200 but empty results - cache None
            if use_cache and page_number == 1:
                save_to_cache(keyword, None)
                print(f"  [Cached 'not found' for '{keyword}']")
            return None

        keyword_lower = keyword.lower()

        # Group matches by exact match vs contains
        exact_matches = []
        contains_matches = []

        for item in results:
            metadata = item.get("metadata", {})
            inci_names = metadata.get("inciName", [])

            if inci_names and inci_names[0]:
                inci_name_lower = inci_names[0].lower()

                if keyword_lower in inci_name_lower:
                    cas_list = metadata.get("casNo", [])
                    cas_no = cas_list[0] if cas_list else None
                    has_valid_cas = cas_no and cas_no != "-"

                    match_info = {
                        "item": item,
                        "inci_name": inci_names[0],
                        "cas_no": cas_no,
                        "has_valid_cas": has_valid_cas
                    }

                    if inci_name_lower == keyword_lower:
                        exact_matches.append(match_info)
                    else:
                        contains_matches.append(match_info)

        # Select best match: prioritize exact matches, then valid CAS, then first result
        candidates = exact_matches if exact_matches else contains_matches

        if candidates:
            # Sort by has_valid_cas (True first)
            candidates.sort(key=lambda x: not x["has_valid_cas"])
            result = candidates[0]["item"]

            # Save to cache
            if use_cache and page_number == 1:
                save_to_cache(keyword, result)
                print(f"  [Cached '{keyword}']")

            return result

        # API returned 200 but no valid matches - cache None
        if use_cache and page_number == 1:
            save_to_cache(keyword, None)
            print(f"  [Cached 'not found' for '{keyword}']")
        return None

    except requests.RequestException as e:
        print(f"Error fetching page {page_number}: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape INCI data for a specific keyword.")
    parser.add_argument("keyword", help="The keyword to search for (e.g. 'aqua')")
    args = parser.parse_args()

    result = fetch_page(args.keyword, 1)
    print(result)
