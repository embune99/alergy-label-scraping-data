#!/usr/bin/env python3
"""
Extract ingredients from product JSON files and append to ingredients.txt
"""

import json
from pathlib import Path
from typing import Set


PRODUCTS_DIR = Path(__file__).parent / "products"
INGREDIENTS_FILE = Path(__file__).parent / "ingredients.txt"


def extract_ingredients_from_file(filepath: Path) -> Set[str]:
    """Extract ingredients from a single product JSON file."""
    import re
    ingredients = set()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw = data.get("inferred_information", {}).get("raw_ingredients")
        if raw:
            # # Some files have prefix like "CREAM: AQUA / WATER • ..." or "1278120 H - COLOURING CREAM: ..."
            # # Extract the part after the last colon if present and it looks like ingredients
            # if ":" in raw and any(sep in raw for sep in [",", "•"]):
            #     # Find the last colon and take everything after it
            #     colon_idx = raw.rfind(":")
            #     raw = raw[colon_idx + 1:].strip()

            # # Split by comma, bullet point (•), or slash (/)
            # # Also handle cases like "AQUA / WATER" - these are alternative names
            # parts = re.split(r"[,•/]", raw)
            # for part in parts:
            #     ingredient = part.strip()
            #     # Filter out non-ingredient text (common prefixes/suffixes)
            #     if ingredient and not ingredient.isdigit() and len(ingredient) > 1:
            #         ingredients.add(ingredient)

            # Regex để match các substring dạng: ". <numbers> [optional letter] - <text>:"
            # re.sub mặc định sẽ thay thế tất cả các match tìm thấy (tương đương với cờ /g trong JS)
            raw = re.sub(r'\.\s*\d+\s*[A-Z]?\s*-\s*[^:\n]+:', ',', raw)

            # Xóa đoạn match ở đầu chuỗi (Dấu ^ định dạng bắt đầu chuỗi)
            raw = re.sub(r'^\d+\s*[A-Z]?\s*-\s*[^:]+:\s*', '', raw)

            # Chuỗi dài cần loại bỏ (gán vào một biến cho dễ nhìn)
            disclaimer = ". “Houd er rekening mee dat de ingrediëntenlijsten voor producten van ons merk regelmatig worden bijgewerkt. Raadpleeg de ingrediëntenlijst op de productverpakking voor de meest actuele lijst met ingrediënten om er zeker van te zijn dat deze geschikt is voor uw persoonlijk gebruik. \" (Voor producten die in de winkel worden bijgevuld, moet de meest actuele ingrediëntenlijst worden verkregen op het verkooppunt nadat het product opnieuw is gevuld)."

            # Thay thế bằng chuỗi rỗng
            raw = raw.replace(disclaimer, "")

            # Thay vì map() và flat() liên tục, dùng re.split để cắt chuỗi 
            # bằng bất kỳ delimiter nào trong: " • ", ": ", " / ", ", "
            results = re.split(r' • |: | / |, ', raw)

            # [...new Set(results)] để lọc trùng lặp
            # Dùng list(set(results)) sẽ lọc trùng nhưng làm lộn xộn thứ tự gốc.
            # Dùng dict.fromkeys() là thủ thuật Pythonic để lọc trùng mà VẪN GIỮ NGUYÊN THỨ TỰ ban đầu.
            ingredients = list(dict.fromkeys(results))

    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading {filepath}: {e}")

    return ingredients


def main():
    # Find all JSON files in products directory
    json_files = list(PRODUCTS_DIR.rglob("*.json"))
    print(f"Found {len(json_files)} product JSON files")

    all_ingredients = set()

    # Extract ingredients from each file
    for filepath in json_files:
        ingredients = extract_ingredients_from_file(filepath)
        all_ingredients.update(ingredients)

    print(f"Extracted {len(all_ingredients)} unique ingredients")

    # Append to ingredients.txt (one per line)
    with open(INGREDIENTS_FILE, "w", encoding="utf-8") as f:
        for ingredient in sorted(all_ingredients):
            f.write(ingredient + "\n")

    print(f"Saved to {INGREDIENTS_FILE}")


if __name__ == "__main__":
    main()
