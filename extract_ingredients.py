#!/usr/bin/env python3
"""
Extract ingredients from product JSON files and add ingredients array field
"""

import json
from pathlib import Path
from typing import List


PRODUCTS_DIR = Path(__file__).parent / "products"


def extract_ingredients_from_file(filepath: Path) -> List[str]:
    """Extract ingredients from a single product JSON file and update it with ingredients field."""
    import re
    ingredients = set()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw = data.get("inferred_information", {}).get("raw_ingredients")

        # Initialize inferred_information if it doesn't exist
        if "inferred_information" not in data:
            data["inferred_information"] = {}
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

            # Remove ingredient-related prefixes (various languages) - anywhere in string
            raw = re.sub(r'INGREDIE?NTS?\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'INGREDIENTEN\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'INGREDIENTES\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'INGREDIËNTEN\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'INGREDIËNTS?\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'INGEDRIENTS?\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'ZUTATEN\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'INGREDIENTI\s*:?\s*', '', raw, flags=re.IGNORECASE)
            # Remove organic farming notes
            raw = re.sub(r'Ingredients? from Organic Farming.*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'Ingredients? stick\s*:.*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'Ingrédients issues de l\'Agriculture Biologique.*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'Ingrédients issus [\'d]e l\'Agriculture Biologique.*', '', raw, flags=re.IGNORECASE)
            # Remove "Ingrediënten:" prefix (Dutch for "Ingredients:") - anywhere in string
            raw = re.sub(r'.*?Ingrediënten\s*:?\s*', '', raw, flags=re.IGNORECASE)
            # Remove "Fair Trade Ingredient" patterns
            raw = re.sub(r'Fair Trade Ingredient\s*\|?\s*Natural ingredients may vary in color and consistency.*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'Fair Trade Ingredient\s*\|?\s*Natural ingredients may vary.*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'Fair Trade Ingredient\s*', '', raw, flags=re.IGNORECASE)
            # Remove "DO NOT USE" (case-insensitive)
            raw = re.sub(r'DO NOT USE\s*', '', raw, flags=re.IGNORECASE)
            # Remove product name prefixes followed by colon (e.g., "WAX STRIPS:")
            raw = re.sub(r'^[A-Z][A-Z\s]{5,}:\s*', '', raw)
            # Remove "+/- may contain" and "may contain" patterns
            raw = re.sub(r'^\+/?\s*-\s*may\s+contain\s*:?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'^may\s+contain\s*:?\s*', '', raw, flags=re.IGNORECASE)
            # Remove content in parentheses (e.g., "(F.I.L. N70016807/1)")
            raw = re.sub(r'\([^)]*\)', '', raw)
            # Remove concentration patterns - must include % or w/w/w/v/v/v indicator (not CI + number)
            # Split approach: protect CI + number patterns first, then remove concentrations, then restore
            ci_placeholders = {}
            def protect_ci_patterns(m):
                placeholder = f"__CI_{len(ci_placeholders)}__"
                ci_placeholders[placeholder] = m.group(0)
                return placeholder
            raw = re.sub(r'CI\s+\d+[A-Za-z]?', protect_ci_patterns, raw)
            # Now remove concentrations (safe since CI patterns are protected)
            raw = re.sub(r'\d+[,.]?\d*\s*(?:%|w/w|w/v|v/v)\s*(?:&?\s*\d+[,.]?\d*\s*(?:%|w/w|w/v|v/v)\s*)?', '', raw)
            raw = re.sub(r'\d+\s+ppm\b', '', raw)
            # Restore CI patterns
            for placeholder, original in ci_placeholders.items():
                raw = raw.replace(placeholder, original)
            # Remove Dutch "Bevat" (contains) statements with ingredient concentrations
            raw = re.sub(r'Bevat\s+[^.:]+\d+%.*', '', raw, flags=re.IGNORECASE)
            # Replace literal \n with actual newlines for splitting
            raw = raw.replace('\\n', '\n')
            # Replace multiple spaces with single space
            raw = re.sub(r' +', ' ', raw)
            raw = raw.strip()

            # Cascading split: ● -> " / " -> " , " -> ", "
            def cascade_split(text: str) -> List[str]:
                results = [text]
                # Split by newlines first
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('\n') if s.strip()])
                results = temp
                # Split by ● first
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('●') if s.strip()])
                results = temp

                # Then split by " · "
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(' · ') if s.strip()])
                results = temp

                # Then split by "· "
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('· ') if s.strip()])
                results = temp

                # Then split by " * "
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(' * ') if s.strip()])
                results = temp

                # Then split by "*"
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('*') if s.strip()])
                results = temp

                # Then split by "•"
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('•') if s.strip()])
                results = temp

                # Then split by " - "
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(' - ') if s.strip()])
                results = temp

                # Then split by "- " (dash without leading space)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('- ') if s.strip()])
                results = temp

                # Then split by " – " (en-dash with spaces)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(' – ') if s.strip()])
                results = temp

                # Then split by ". " (dot-space separator)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('. ') if s.strip()])
                results = temp

                # Then split by " / "
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(' / ') if s.strip()])
                results = temp

                # Then split by "/"
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('/') if s.strip()])
                results = temp

                # Then split by "\\" (backslash - alternative names)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split('\\') if s.strip()])
                results = temp

                # Then split by " , " (space before comma)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(' , ') if s.strip()])
                results = temp

                # Then split by ", " (space before comma)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(', ') if s.strip()])
                results = temp

                # Finally split by "," (comma only)
                temp = []
                for r in results:
                    temp.extend([s.strip() for s in r.split(',') if s.strip()])
                results = temp

                return results

            results = cascade_split(raw)

            # Filter out optional ingredients (starting with [ or +, ending with [+)
            def is_optional(item: str) -> bool:
                item_lower = item.lower()
                return (item.startswith('[') or item.startswith('+') or
                        item.endswith('[+') or
                        item_lower.startswith('may contain') or
                        item_lower.startswith('+/') or
                        item.startswith('-'))

            results = [r for r in results if r and not is_optional(r)]

            # Post-process: remove leading slashes, trailing dots, orphaned parentheses, filter empty
            def clean_ingredient(i: str) -> str:
                i = i.lstrip('/').lstrip('°').lstrip("'").lstrip(":").lstrip("s: ").lstrip("wax: ").lstrip("| ").lstrip("® ").lstrip("¹ ")  # Remove leading slash and degree symbol
                # Remove everything from opening parenthesis to end (if no closing)
                if '(' in i and ')' not in i:
                    i = i[:i.index('(')]
                # Remove everything up to orphaned closing parenthesis (if no opening)
                if ')' in i and '(' not in i:
                    i = i[i.index(')') + 1:]
                # Remove everything from opening bracket to end (if no closing)
                if '[' in i and ']' not in i:
                    i = i[:i.index('[')]
                i = i.strip()  # Strip whitespace first to handle "char] ." cases
                i = i.rstrip('.').rstrip(']').rstrip(',').rstrip('°').rstrip('+')  # Remove trailing dot, bracket, comma
                i = i.strip()
                # Remove orphaned closing bracket at end (if no opening)
                if i.endswith(']') and '[' not in i:
                    i = i.rstrip(']')
                return i.strip()

            def is_valid_ingredient(i: str) -> bool:
                if i == "C-":
                    return False
                # Filter out symbols-only or very short meaningless strings
                if not i or len(i) < 2:
                    return False
                # Check if contains at least one letter
                if not any(c.isalpha() for c in i):
                    return False
                return True

            # Clean all ingredients first, then filter and deduplicate
            cleaned = [clean_ingredient(i) for i in results]
            ingredients = list(dict.fromkeys(i for i in cleaned if i and is_valid_ingredient(i)))

            # Add ingredients field to the JSON
            data["inferred_information"]["ingredients"] = ingredients

            # Write back to the file
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"Updated {filepath.name} with {len(ingredients)} ingredients")

    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading {filepath}: {e}")

    return ingredients


def main():
    # Find all JSON files in products directory
    json_files = list(PRODUCTS_DIR.rglob("*.json"))
    print(f"Found {len(json_files)} product JSON files")

    all_ingredients = set()

    # Extract ingredients from each file and update with ingredients field
    for filepath in json_files:
        ingredients = extract_ingredients_from_file(filepath)
        all_ingredients.update(ingredients)

    print(f"\nExtracted {len(all_ingredients)} unique ingredients across all files")

    # Save to ingredients.txt (overwrite old data)
    output_file = Path(__file__).parent / "ingredients.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        for ingredient in sorted(all_ingredients):
            f.write(f"{ingredient}\n")
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()
