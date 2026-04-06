import json
import os
from collections import defaultdict
from pathlib import Path


def build_inci_mapping():
    """Build a mapping from INCI names to ingredient keys."""
    mapping = defaultdict(set)

    # Loop through all product JSON files
    products_dir = Path("products/dermacare")
    for product_file in products_dir.glob("*.json"):
        if product_file.name == "_meta.json":
            continue

        try:
            with open(product_file, 'r') as f:
                data = json.load(f)

            # Check if the product has inferred_information.inci
            inci = data.get("inferred_information", {}).get("inci", {})
            if not inci:
                continue

            # Loop through each ingredient key
            for key, value in inci.items():
                cosing_info = value.get("cosing_info")
                if cosing_info and cosing_info.get("inci_name"):
                    inci_name = cosing_info["inci_name"]
                    mapping[inci_name].add(key)

        except Exception as e:
            print(f"Error processing {product_file}: {e}")

    # Convert sets to sorted lists
    result = {k: sorted(list(v)) for k, v in sorted(mapping.items())}

    # Output to JSON file
    output_file = "inci_mapping.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Generated {output_file} with {len(result)} INCI mappings")

    # Print some stats
    print("\nTop 10 INCI names with most ingredient keys:")
    for inci_name, keys in sorted(result.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"  {inci_name}: {len(keys)} keys - {keys[:5]}{'...' if len(keys) > 5 else ''}")

    return result


if __name__ == "__main__":
    build_inci_mapping()
