import json
import uuid
import os
import glob

PRODUCTS_DIR = "products"
OUTPUT_FILE = "migration.sql"
SOURCE = "ETOS"
LANGUAGE = "nl"

def escape_sql(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"

def main():
    json_files = glob.glob(os.path.join(PRODUCTS_DIR, "**", "*.json"), recursive=True)
    print(f"Found {len(json_files)} product files")

    with open(OUTPUT_FILE, "w") as f:
        f.write("-- Migration generated from ETOS product data\n")
        f.write("-- Total products: {}\n\n".format(len(json_files)))

        for filepath in json_files:
            with open(filepath, "r") as jf:
                try:
                    data = json.load(jf)
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON: {filepath}")
                    continue

            product_info = data.get("product_information", {})
            additional_info = data.get("additional_information", {})

            source_product_id = additional_info.get("id", "")
            product_url = product_info.get("product_url", "")
            name = product_info.get("product_name", "")
            price = product_info.get("price", "")

            master_id = str(uuid.uuid4())
            source_id = str(uuid.uuid4())

            f.write(
                f"INSERT INTO PRODUCT_MASTER (Id, ExternalId, BrandId, NormalizedName, IngredientFingerprint, MergeStatus, CreatedAt, UpdatedAt) "
                f"VALUES ({escape_sql(master_id)}, NULL, NULL, NULL, NULL, NULL, NOW(), NOW());\n"
            )

            f.write(
                f"INSERT INTO PRODUCT_SOURCE (Id, ProductMasterId, Source, SourceProductId, ProductUrl, Name, Price, InStock, Language, Tags, CreatedAt, UpdatedAt) "
                f"VALUES ({escape_sql(source_id)}, {escape_sql(master_id)}, {escape_sql(SOURCE)}, {escape_sql(source_product_id)}, "
                f"{escape_sql(product_url)}, {escape_sql(name)}, {escape_sql(price)}, TRUE, {escape_sql(LANGUAGE)}, NULL, NOW(), NOW());\n\n"
            )

    print(f"Generated {OUTPUT_FILE} with {len(json_files)} products")

if __name__ == "__main__":
    main()
