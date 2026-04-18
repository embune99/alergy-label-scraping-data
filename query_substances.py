#!/usr/bin/env python3
"""
Query CosIng API for substance IDs.
Starts from init=27934, checks existing substance_ids.txt,
queries new IDs, saves results to inci/ folder.
Stops when total count reaches 36249.
"""

import json
import time
import requests
from pathlib import Path

# Configuration
BASE_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "285a77fd-1257-4271-8507-f0c6b2961203"
INCI_DIR = Path(__file__).parent / "inci"
SUBSTANCE_IDS_FILE = Path(__file__).parent / "substance_ids.txt"
EMPTY_IDS_FILE = Path(__file__).parent / "substance_ids_empty.txt"
INIT = 27934
TARGET_TOTAL = 36249
PAGE_SIZE = 1

# Request headers
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en,vi;q=0.9,to;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "No-Cache",
    "Connection": "keep-alive",
    "Origin": "https://ec.europa.eu",
    "Referer": "https://ec.europa.eu/"
}


def load_existing_ids() -> set:
    """Load existing substance IDs from substance_ids.txt."""
    if not SUBSTANCE_IDS_FILE.exists():
        return set()
    with open(SUBSTANCE_IDS_FILE, "r", encoding="utf-8") as f:
        return {int(line.strip()) for line in f if line.strip()}


def load_empty_ids() -> set:
    """Load substance IDs that have no results from CosIng."""
    if not EMPTY_IDS_FILE.exists():
        return set()
    with open(EMPTY_IDS_FILE, "r", encoding="utf-8") as f:
        return {int(line.strip()) for line in f if line.strip()}


def build_query(substance_id: int) -> dict:
    """Build query payload for CosIng API."""
    return {
        "bool": {
            "must": [
                {
                    "text": {
                        "query": str(substance_id),
                        "fields": ["substanceId.exact"],
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


def fetch_substance(substance_id: int) -> list | None:
    """Fetch substance data from CosIng API."""
    params = {
        "apiKey": API_KEY,
        "text": "*",
        "pageSize": PAGE_SIZE,
        "pageNumber": 1
    }

    query_payload = build_query(substance_id)
    files = {
        "query": ("blob", json.dumps(query_payload), "application/json")
    }

    try:
        response = requests.post(BASE_URL, params=params, headers=HEADERS, files=files, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.RequestException as e:
        print(f"  [Error fetching {substance_id}: {e}]")
        return None


def save_item(item: dict) -> None:
    """Save item to JSON file named by item.reference."""
    reference = item.get("reference")
    if not reference:
        print(f"  [Item has no reference, skipping]")
        return

    output_path = INCI_DIR / f"{reference}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(item, f, indent=2, ensure_ascii=False)


def append_substance_id(substance_id: int) -> None:
    """Append substance ID to substance_ids.txt."""
    with open(SUBSTANCE_IDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{substance_id}\n")


def append_empty_id(substance_id: int) -> None:
    """Append substance ID to substance_ids_empty.txt."""
    with open(EMPTY_IDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{substance_id}\n")


def main():
    INCI_DIR.mkdir(exist_ok=True)

    existing_ids = load_existing_ids()
    empty_ids = load_empty_ids()
    current_count = len(existing_ids)
    print(f"Loaded {current_count} existing substance IDs")
    print(f"Loaded {len(empty_ids)} empty IDs (will skip)")
    print(f"Target: {TARGET_TOTAL}, need: {TARGET_TOTAL - current_count}")

    count = 0
    substance_id = INIT

    while current_count + count < TARGET_TOTAL:
        # Skip if already exists or known empty
        if substance_id in existing_ids:
            print(f"[{substance_id}] already exists, skipping...")
            substance_id += 1
            continue

        if substance_id in empty_ids:
            print(f"[{substance_id}] known empty, skipping...")
            substance_id += 1
            continue

        print(f"[{substance_id}] querying CosIng...", end=" ")
        results = fetch_substance(substance_id)

        if results is None:
            # Error occurred, skip this ID
            substance_id += 1
            # time.sleep(1)
            continue

        if not results:
            print("no results")
            append_empty_id(substance_id)
            substance_id += 1
            # time.sleep(5)
            continue

        # Save each item
        for item in results:
            save_item(item)

        # Get substanceId from first result and append
        metadata = results[0].get("metadata", {})
        substance_ids = metadata.get("substanceId", [])
        if substance_ids:
            found_id = int(substance_ids[0])
            append_substance_id(found_id)
            count += 1
            print(f"saved {len(results)} item(s), total new: {count}")
        else:
            print("no substanceId in metadata")

        substance_id += 1
        # time.sleep(5)

    print(f"\nDone! Total: {current_count + count}/{TARGET_TOTAL}")


if __name__ == "__main__":
    main()
