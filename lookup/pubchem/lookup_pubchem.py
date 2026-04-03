#!/usr/bin/env python3
"""
Lookup chemical data from PubChem API.
Supports search by name or CAS number.
"""

import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

# API Configuration
BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CACHE_DIR = Path(__file__).parent / "cache"
REQUEST_DELAY = 0.1  # PubChem is more lenient

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


def search_by_name(name: str, use_cache: bool = True) -> List[Dict[str, Any]]:
    """Search PubChem by compound name. Returns list of results with cid, sid."""
    # Check cache
    if use_cache:
        cached = load_from_cache(f"name_{name}")
        if cached:
            return cached.get("results", [])

    results = []

    try:
        # Step 1: Search for CID
        search_url = f"{BASE_URL}/compound/name/{requests.utils.quote(name)}/cids/JSON"
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()

        data = response.json()
        cids = data.get("IdentifierList", {}).get("CID", [])

        if not cids:
            # Save empty result to cache
            if use_cache:
                save_to_cache(f"name_{name}", {"results": []})
            return []

        # Step 2: Get details for each CID
        for cid in cids[:5]:  # Limit to first 5 results
            try:
                # Get SID (substance IDs)
                sid_url = f"{BASE_URL}/compound/cid/{cid}/sids/JSON"
                sid_response = requests.get(sid_url, timeout=10)
                sid_response.raise_for_status()
                sid_data = sid_response.json()
                sids = sid_data.get("InformationList", {}).get("Information", [])
                sid = sids[0].get("SID") if sids else None

                results.append({
                    "cid": str(cid),
                    "sid": str(sid) if sid else None
                })

                time.sleep(REQUEST_DELAY)
            except Exception:
                results.append({"cid": str(cid), "sid": None})

        # Save to cache
        if use_cache:
            save_to_cache(f"name_{name}", {"results": results})

        return results

    except Exception as e:
        print(f"    [PubChem error for '{name}': {e}]")
        return []


def search_by_cas(cas_no: str, use_cache: bool = True) -> List[Dict[str, Any]]:
    """Search PubChem by CAS number. Returns list of results with cid, sid."""
    # Check cache
    if use_cache:
        cached = load_from_cache(f"cas_{cas_no}")
        if cached:
            return cached.get("results", [])

    results = []

    try:
        # Step 1: Search for CID using CAS
        search_url = f"{BASE_URL}/compound/name/{requests.utils.quote(cas_no)}/cids/JSON"
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()

        data = response.json()
        cids = data.get("IdentifierList", {}).get("CID", [])

        if not cids:
            if use_cache:
                save_to_cache(f"cas_{cas_no}", {"results": []})
            return []

        # Step 2: Get details for each CID
        for cid in cids[:3]:
            try:
                sid_url = f"{BASE_URL}/compound/cid/{cid}/sids/JSON"
                sid_response = requests.get(sid_url, timeout=10)
                sid_response.raise_for_status()
                sid_data = sid_response.json()
                sids = sid_data.get("InformationList", {}).get("Information", [])
                sid = sids[0].get("SID") if sids else None

                results.append({
                    "cid": str(cid),
                    "sid": str(sid) if sid else None,
                    "cas_no": cas_no
                })

                time.sleep(REQUEST_DELAY)
            except Exception:
                results.append({"cid": str(cid), "sid": None, "cas_no": cas_no})

        # Save to cache
        if use_cache:
            save_to_cache(f"cas_{cas_no}", {"results": results})

        return results

    except Exception as e:
        print(f"    [PubChem error for CAS '{cas_no}': {e}]")
        return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lookup PubChem data.")
    parser.add_argument("query", help="Name or CAS number to search")
    parser.add_argument("--type", choices=["name", "cas"], default="name", help="Search type")
    args = parser.parse_args()

    if args.type == "cas":
        result = search_by_cas(args.query)
    else:
        result = search_by_name(args.query)

    print(json.dumps(result, indent=2))
