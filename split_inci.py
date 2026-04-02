import json
import os

# Read inci.json
with open('inci.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Create inci folder if it doesn't exist
os.makedirs('inci', exist_ok=True)

# Iterate through the data
for ingredient_name, items in data.items():
    for item in items:
        reference = item.get('reference')
        if reference:
            # Save each item as {reference}.json
            file_path = os.path.join('inci', f'{reference}.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=2, ensure_ascii=False)
            print(f'Created: {file_path}')

print(f'Total files created: {sum(len(items) for items in data.values())}')
