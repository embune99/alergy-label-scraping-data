#!/usr/bin/env python3
"""
Lookup chemical data from PubChem API.
Searches by keyword (name or CAS number).
"""

import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# API Configuration
BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CACHE_DIR = Path(__file__).parent / "cache"
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)


def sanitize_filename(keyword: str) -> str:
    """Sanitize keyword to be used as a filename."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', keyword)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


def get_cache_path(identifier: str) -> Path:
    """Get the cache file path for an identifier."""
    filename = sanitize_filename(identifier) + ".json"
    return CACHE_DIR / filename


def load_from_cache(identifier: str) -> Dict[str, Any] | None:
    """Load cached response if available."""
    cache_path = get_cache_path(identifier)
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_to_cache(identifier: str, data: Dict[str, Any]) -> None:
    """Save response to cache."""
    cache_path = get_cache_path(identifier)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_sid_from_cid(cid: str) -> Optional[str]:
    """Get SID from CID using pug_view endpoint with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            url = f"{BASE_URL}_view/data/compound/{cid}/JSON/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            sections = data.get("Record", {}).get("Section", [])

            for section in sections:
                if section.get("TOCHeading") == "Related Records":
                    for subsection in section.get("Section", []):
                        if subsection.get("TOCHeading") == "Substances":
                            for subsubsection in subsection.get("Section", []):
                                if "SID" in subsubsection.get("TOCHeading", ""):
                                    info = subsubsection.get("Information", [])
                                    if info and info[0].get("Value", {}).get("Number"):
                                        return str(info[0]["Value"]["Number"][0])

            return None

        except (requests.HTTPError, requests.ConnectionError, requests.RequestException) as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    [Retry {attempt + 1}/{MAX_RETRIES} for CID {cid}: {type(e).__name__}]")
                time.sleep(RETRY_DELAY)
                continue
            return None
        except Exception:
            return None

    return None


def search(keyword: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """Search PubChem by keyword (name or CAS). Returns dict with cid, sid or None."""
    # Check cache
    if use_cache:
        cached = load_from_cache(keyword)
        if cached:
            return cached

    for attempt in range(MAX_RETRIES):
        try:
            # Step 1: Search for CID using disambiguate endpoint
            search_url = f"{BASE_URL}/disambiguate/name/JSON?name={requests.utils.quote(keyword)}"
            response = requests.get(search_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            records = data.get("Disambiguation", {}).get("Record", [])

            # Filter for Compound records - take first CID only
            cid = None
            for record in records:
                if record.get("RecordType") == "Compound":
                    cid = record.get("IntID")
                    break

            if not cid:
                # Save empty result to cache
                if use_cache:
                    save_to_cache(keyword, None)
                return None

            # Step 2: Get SID for the CID (has its own retry logic)
            sid = get_sid_from_cid(cid)

            result = {
                "cid": str(cid),
                "sid": sid
            }

            # Save to cache
            if use_cache:
                save_to_cache(keyword, result)

            return result

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    [Retry {attempt + 1}/{MAX_RETRIES} for '{keyword}': {type(e).__name__}]")
                time.sleep(RETRY_DELAY)
                continue
            print(f"    [PubChem error for '{keyword}': {e}]")
            return None

    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lookup PubChem data.")
    parser.add_argument("query", help="Keyword to search (name or CAS)")
    args = parser.parse_args()

    result = search(args.query)
    print(json.dumps(result, indent=2))
