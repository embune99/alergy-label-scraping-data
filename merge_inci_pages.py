#!/usr/bin/env python3
"""
Merge all page_xxx.json files from inci_pages/ into a single inci.json file.
Deduplicates items based on the 'reference' field.
"""
import json
from pathlib import Path


def merge_inci_pages():
    inci_dir = Path("inci_pages")
    output_file = Path("inci.json")

    # Dictionary to store unique items by reference
    unique_items = {}

    # Read all page_xxx.json files
    for page_file in sorted(inci_dir.glob("page_*.json")):
        print(f"Processing {page_file.name}...")
        try:
            with open(page_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extract results array
            results = data.get("results", [])
            for item in results:
                ref = item.get("reference")
                if ref:
                    # Only keep the first occurrence of each reference
                    if ref not in unique_items:
                        unique_items[ref] = item
        except json.JSONDecodeError as e:
            print(f"  Error reading {page_file.name}: {e}")

    # Convert to array
    items_array = list(unique_items.values())

    # Write output
    print(f"\nWriting {len(items_array)} unique items to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(items_array, f, ensure_ascii=False, indent=2)

    print(f"Done! Total items: {len(items_array)}")


if __name__ == "__main__":
    merge_inci_pages()
