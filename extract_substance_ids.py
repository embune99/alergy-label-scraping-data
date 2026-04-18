import json
import os

inci_folder = "/home/embune/Desktop/code/alergy-label/crawler/etos.nl/inci"
substance_ids = []

for filename in os.listdir(inci_folder):
    if filename.endswith(".json"):
        filepath = os.path.join(inci_folder, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            substance_id = data.get("metadata", {}).get("substanceId", [None])[0]
            if substance_id:
                substance_ids.append(int(substance_id))

substance_ids.sort()

output_file = "/home/embune/Desktop/code/alergy-label/crawler/etos.nl/substance_ids.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for sid in substance_ids:
        f.write(f"{sid}\n")

print(f"Extracted {len(substance_ids)} substance IDs to {output_file}")
