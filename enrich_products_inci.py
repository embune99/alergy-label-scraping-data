#!/usr/bin/env python3
"""
Enrich product JSON files with INCI data from CosIng API and PubChem API.
Updates inferred_information.inci with structured cosing_info and pubchem_info.
Tracks enriched_count in category _meta.json files.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys

# Add lookup directories to path
LOOKUP_DIR = Path(__file__).parent / "lookup"
sys.path.insert(0, str(LOOKUP_DIR / "cosing"))
sys.path.insert(0, str(LOOKUP_DIR / "pubchem"))

from lookup_cosing import fetch_page as cosing_fetch
from lookup_pubchem import search_by_name as pubchem_search_name
from lookup_pubchem import search_by_cas as pubchem_search_cas

# Configuration
PRODUCTS_DIR = Path(__file__).parent / "products"
REQUEST_DELAY = 0.5  # seconds between CosIng requests


def get_category_meta(product_path: Path) -> tuple[Path, Dict[str, Any]]:
    """Get the meta file path and data for the product's category."""
    category_dir = product_path.parent
    meta_path = category_dir / "_meta.json"

    if meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return meta_path, json.load(f)
        except Exception:
            pass

    # Return default meta structure if not exists
    return meta_path, {
        "category_url": "",
        "slug": category_dir.name,
        "crawled_product_urls": 0,
        "processed_count": 0,
        "enriched_count": 0
    }


def update_meta_enriched_count(meta_path: Path, meta_data: Dict[str, Any]) -> None:
    """Update the enriched_count in meta file."""
    meta_data["enriched_count"] = meta_data.get("enriched_count", 0) + 1

    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  [Warning: Could not update meta file: {e}]")


def extract_cosing_info(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract relevant info from CosIng API response."""
    if not item:
        return None

    metadata = item.get("metadata", {})
    reference = item.get("reference", "")
    inci_names = metadata.get("inciName", [])
    inci_name = inci_names[0] if inci_names else ""
    cas_no_raw = metadata.get("casNo", [])

    # Split CAS numbers by " / " and flatten the list
    cas_no = []
    for cas in cas_no_raw:
        if isinstance(cas, str):
            cas_no.extend([c.strip() for c in cas.split(" / ") if c.strip()])
        else:
            cas_no.append(cas)

    return {
        "cosing_info": {
            "reference": reference,
            "inci_name": inci_name,
            "cas_no": cas_no
        }
    }


def fetch_pubchem_info(ingredient: str, inci_name: Optional[str] = None, cas_list: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Fetch PubChem data for an ingredient.

    Args:
        ingredient: Original ingredient name from product
        inci_name: INCI name from CosIng (if available)
        cas_list: List of CAS numbers from CosIng (if available)

    Returns:
        List of PubChem info objects with cid, sid, cas_no
    """
    pubchem_results = []

    try:
        # Case 1: Has CAS numbers - search by each CAS
        if cas_list:
            for cas in cas_list:
                if cas and cas != "-":
                    print(f"    → PubChem lookup by CAS: {cas}")
                    results = pubchem_search_cas(cas)
                    if results:
                        pubchem_results.extend(results)
                    time.sleep(0.1)

        # Case 2: No CAS but has INCI name - search by INCI name
        elif inci_name:
            print(f"    → PubChem lookup by INCI name: {inci_name}")
            results = pubchem_search_name(inci_name)
            if results:
                # Add empty cas_no to results from name search
                for r in results:
                    r["cas_no"] = None
                pubchem_results.extend(results)

        # Case 3: No CosIng data at all - search by original ingredient name
        else:
            print(f"    → PubChem lookup by ingredient name: {ingredient}")
            results = pubchem_search_name(ingredient)
            if results:
                for r in results:
                    r["cas_no"] = None
                pubchem_results.extend(results)

    except Exception as e:
        print(f"    [PubChem error: {e}]")

    return pubchem_results


def enrich_product(product_path: Path) -> bool:
    """Enrich a single product JSON with INCI and PubChem data."""
    # Get category meta for tracking
    meta_path, meta_data = get_category_meta(product_path)

    try:
        with open(product_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {product_path}: {e}")
        return False

    inferred = data.get("inferred_information", {})
    ingredients = inferred.get("ingredients", [])

    if not ingredients:
        print(f"Skipping {product_path.name}: no ingredients found")
        return False

    # Initialize inci dict if not exists
    if "inci" not in inferred:
        inferred["inci"] = {}

    inci_data = {}
    success_count = 0

    for ingredient in ingredients:
        ingredient_clean = ingredient.strip().strip(',')

        if not ingredient_clean:
            continue

        print(f"  Looking up: {ingredient_clean}")

        # Step 1: Fetch from CosIng API
        cosing_result = cosing_fetch(ingredient_clean, 1)

        if cosing_result:
            # CosIng found - extract info and lookup PubChem with CAS or INCI name
            cosing_info = extract_cosing_info(cosing_result)
            if cosing_info:
                inci_name = cosing_info["cosing_info"]["inci_name"]
                cas_list = cosing_info["cosing_info"]["cas_no"]

                # Fetch PubChem data using CAS or INCI name
                pubchem_info = fetch_pubchem_info(ingredient_clean, inci_name, cas_list)

                # Add pubchem_info to the result
                cosing_info["pubchem_info"] = pubchem_info

                inci_data[ingredient_clean.lower()] = cosing_info
                success_count += 1

                print(f"    ✓ CosIng: {inci_name}")
                if pubchem_info:
                    print(f"    ✓ PubChem: {len(pubchem_info)} result(s)")
                else:
                    print(f"    ✗ PubChem: No results")
            else:
                print(f"    ✗ No valid CosIng data extracted")
        else:
            # CosIng not found - lookup PubChem by ingredient name
            print(f"    ✗ CosIng: Not found")
            pubchem_info = fetch_pubchem_info(ingredient_clean)

            if pubchem_info:
                inci_data[ingredient_clean.lower()] = {
                    "cosing_info": None,
                    "pubchem_info": pubchem_info
                }
                success_count += 1
                print(f"    ✓ PubChem: {len(pubchem_info)} result(s)")
            else:
                print(f"    ✗ PubChem: No results")

        # Respectful delay for CosIng
        time.sleep(REQUEST_DELAY)

    # Update the data
    inferred["inci"] = inci_data
    data["inferred_information"] = inferred

    # Write back to file
    try:
        with open(product_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Updated {product_path.name}: {success_count}/{len(ingredients)} ingredients")

        # Update meta enriched_count
        update_meta_enriched_count(meta_path, meta_data)
        print(f"  [Meta updated: enriched_count = {meta_data['enriched_count']}]")

        return True
    except Exception as e:
        print(f"Error writing {product_path}: {e}")
        return False


def main():
    """Enrich all product JSON files."""
    # Get all product JSON files, excluding _meta.json
    json_files = [f for f in PRODUCTS_DIR.rglob("*.json") if f.name != "_meta.json"]

    if not json_files:
        print(f"No JSON files found in {PRODUCTS_DIR}")
        return

    print(f"Found {len(json_files)} product files to process")

    for i, product_path in enumerate(json_files, 1):
        print(f"\n[{i}/{len(json_files)}] Processing: {product_path.relative_to(PRODUCTS_DIR)}")
        enrich_product(product_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
