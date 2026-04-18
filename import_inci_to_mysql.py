import json
import os
import uuid
from datetime import datetime
import mysql.connector
from typing import Optional, Dict, Any, List

# MySQL connection configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '100699',
    'database': 'acn_datascraping_primary'
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def get_first_value(arr: List[Any]) -> Optional[str]:
    """Get first non-empty value from array, or None if array is empty"""
    if arr and len(arr) > 0:
        val = arr[0]
        if val is not None and val != "" and val != "-":
            return str(val)
    return None

def get_valid_cas_number(arr: List[Any]) -> Optional[str]:
    """Get first valid CAS number (not empty and not '-')"""
    if arr:
        for item in arr:
            val = str(item).strip() if item is not None else ""
            if val and val != "-":
                return val
    return None

def check_duplicate_inci_id(cursor, inci_id: str) -> bool:
    """Check if InciId already exists in database"""
    cursor.execute("SELECT Id FROM Incis WHERE InciId = %s", (inci_id,))
    return cursor.fetchone() is not None

def parse_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Parse JSON file and extract required fields"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata = data.get('metadata', {})

        inci_name = get_first_value(metadata.get('inciName', []))
        inci_id = get_first_value(metadata.get('substanceId', []))
        cas_number = get_valid_cas_number(metadata.get('casNo', []))
        description = get_first_value(metadata.get('chemicalDescription', []))

        if not inci_id:
            print(f"Skipping {file_path}: missing InciId")
            return None

        return {
            'inci_name': inci_name,
            'inci_id': inci_id,
            'cas_number': cas_number,
            'description': description
        }
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def insert_to_db(cursor, data: Dict[str, Any]) -> bool:
    """Insert data into Incis table"""
    try:
        now = datetime.now()
        record_id = str(uuid.uuid4())

        query = """
            INSERT INTO Incis (Id, InciName, InciId, CASNumber, Description, CreatedAt, UpdatedAt)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            record_id,
            data['inci_name'],
            data['inci_id'],
            data['cas_number'],
            data['description'],
            now,
            now
        ))
        return True
    except Exception as e:
        print(f"Error inserting record: {e}")
        return False

def main():
    inci_folder = 'inci'

    if not os.path.exists(inci_folder):
        print(f"Folder '{inci_folder}' not found!")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        json_files = [f for f in os.listdir(inci_folder) if f.endswith('.json')]
        total_files = len(json_files)
        inserted_count = 0
        skipped_count = 0
        duplicate_count = 0

        print(f"Found {total_files} JSON files")
        print("-" * 50)

        batch_size = 1000
        for filename in json_files:
            file_path = os.path.join(inci_folder, filename)
            parsed_data = parse_json_file(file_path)

            if parsed_data is None:
                skipped_count += 1
                continue

            # Check for duplicate
            if check_duplicate_inci_id(cursor, parsed_data['inci_id']):
                print(f"Duplicate InciId {parsed_data['inci_id']} in {filename} - skipping")
                duplicate_count += 1
                continue

            # Insert to database
            if insert_to_db(cursor, parsed_data):
                inserted_count += 1
                print(f"[{inserted_count}] Inserted: {parsed_data['inci_name']} ({parsed_data['inci_id']})")

            # Commit periodically
            if inserted_count % batch_size == 0:
                conn.commit()
                print(f"--- Committed batch at {inserted_count} records ---")

        conn.commit()

        print("-" * 50)
        print(f"Summary:")
        print(f"  Total files: {total_files}")
        print(f"  Inserted: {inserted_count}")
        print(f"  Duplicates skipped: {duplicate_count}")
        print(f"  Parse errors: {skipped_count}")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
