#!/usr/bin/env python3
"""
Script to loop through product JSON files, extract inferred_information.ingredients,
and map them to INCI records. Uses local inci.json as a cache mapping ingredient
names to API results. If not found in cache, falls back to the European Commission
API using scrape_inci.py.
"""

import json
import logging
from pathlib import Path
import sys
import time

# Ensure scrape_inci can be imported
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
import scrape_inci

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_inci_data(inci_path: Path):
    if not inci_path.exists() or inci_path.stat().st_size == 0:
        logging.info("inci.json is empty or not found, initializing empty dict.")
        return {}
    
    try:
        with open(inci_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logging.warning("inci.json is not a dictionary. Reinitializing empty dict.")
                return {}
            return data
    except json.JSONDecodeError as e:
        logging.info(f"inci.json contains invalid JSON: {e}. Initializing empty dict.")
        return {}
    except Exception as e:
        logging.error(f"Failed to load inci.json: {e}")
        return {}


def save_inci_data(inci_path: Path, data: dict):
    with open(inci_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def process_product(product_path: Path, inci_data: dict, save_interval=100):
    try:
        with open(product_path, 'r', encoding='utf-8') as f:
            product = json.load(f)
    except Exception as e:
        logging.error(f"Error reading {product_path}: {e}")
        return False

    inferred = product.get("inferred_information", {})
    if not isinstance(inferred, dict):
        return False
        
    ingredients = inferred.get("ingredients", [])
    if not ingredients or not isinstance(ingredients, list):
        return False

    inci_references = set()
    inferred_inci = inferred.get("inci", [])
    if isinstance(inferred_inci, list):
        inci_references.update(inferred_inci)
    elif isinstance(inferred_inci, str):
        inci_references.add(inferred_inci)
    
    updated_product = False
    inci_data_updated = False
    
    for ingredient in ingredients:
        if not ingredient or not isinstance(ingredient, str):
            continue
            
        search_term = ingredient.lower().replace('\n', ' ').strip()
        
        # Check if the search term is already in the cache (inci_data)
        if search_term in inci_data:
            # Get from local cache
            api_items = inci_data[search_term]
            logging.info(f"[{product_path.name}] '{search_term}' found in cache ({len(api_items)} items).")
        else:
            # Not in cache, fetch from API
            logging.info(f"[{product_path.name}] '{search_term}' not in cache. Calling API...")
            try:
                # fetch the first page from API
                api_result = scrape_inci.fetch_page(search_term, 1)
                
                # We save the 'results' array which has the items with their 'reference'
                api_items = api_result.get("results", []) if api_result else []
                
                # Save to cache regardless of whether it's empty or full
                inci_data[search_term] = api_items
                inci_data_updated = True
                
                logging.info(f"  -> API found {len(api_items)} items for '{search_term}'")
                time.sleep(0.5) # simple rate limit to be polite
                
            except Exception as e:
                logging.error(f"Failed to fetch from API for '{search_term}': {e}")
                api_items = []
        
        # Process references from the cached items
        added_new_refs = False
        for item in api_items:
            ref = item.get("reference")
            if ref and ref not in inci_references:
                inci_references.add(ref)
                updated_product = True
                added_new_refs = True
            
    # Update the product if any new references were added, or if 'inci' key is missing
    if updated_product or "inci" not in inferred:
        inferred["inci"] = list(inci_references)
        product["inferred_information"] = inferred
        with open(product_path, 'w', encoding='utf-8') as f:
            json.dump(product, f, ensure_ascii=False, indent=2)
            
    return inci_data_updated


def main():
    base_dir = Path(__file__).parent
    inci_path = base_dir / "inci.json"
    products_dir = base_dir / "products"
    
    logging.info("Loading inci.json cache...")
    inci_data = load_inci_data(inci_path)
    
    product_files = list(products_dir.rglob("*.json"))
    logging.info(f"Found {len(product_files)} product files")
    
    inci_needs_save = False
    
    for i, p_file in enumerate(product_files, 1):
        if i % 100 == 0:
            logging.info(f"Processed {i}/{len(product_files)} files...")
            if inci_needs_save:
                logging.info("Saving intermediate inci.json...")
                save_inci_data(inci_path, inci_data)
                inci_needs_save = False

        if process_product(p_file, inci_data):
            inci_needs_save = True
            
    if inci_needs_save:
        logging.info("Saving final inci.json...")
        save_inci_data(inci_path, inci_data)
        
    logging.info("Complete processing!")

if __name__ == "__main__":
    main()
