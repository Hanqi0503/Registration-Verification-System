from flask import current_app
from datetime import datetime
import pandas as pd
from datetime import datetime
import csv, os

def save_to_db(collection_name: str, data: dict) -> dict:
    """
    Save a record to the specified MongoDB collection.

    Args:
        collection_name (str): The name of the MongoDB collection.
        data (dict): The document to be saved.

    Returns:
        dict: The inserted document (with _id).
    """
    db = current_app.db  # uses app.db from your init_db()
    data["created_at"] = datetime.utcnow()

    result = db[collection_name].insert_one(data)
    data["_id"] = str(result.inserted_id)

    print(f"✅ Saved record to '{collection_name}' with ID {data['_id']}")
    return data

def save_to_csv(data: dict) -> bool:
    """
    Append a single record to the CSV file defined in current_app.db['path'].

    Args:
        data (dict): The data to be saved.

    Returns:
        bool: True on success.
    """
    cfg = current_app.db
    df = cfg.get("dataframe")
    if df is None or df.empty:
        print("❌ No dataframe available to save data")
        return False  

    rec = {}
    for col in df.columns:
        if col.lower() == "created_at":
            rec[col] = data.get(col, datetime.utcnow().isoformat())
        else:
            if col in data:
                rec[col] = data[col]
            elif col.lower() in data:
                rec[col] = data[col.lower()]
            else:
                rec[col] = ""

    csv_path = cfg.get("path")
    if csv_path:
        try:
            csv_dir = os.path.dirname(os.fspath(csv_path))
            if csv_dir:
                os.makedirs(csv_dir, exist_ok=True)
            df.to_csv(csv_path, index=False)
        except Exception:
            print("❌ Failed to write to CSV file")
            return False
    return True

def update_to_csv(data: dict, match_column: str, match_value) -> bool:
    """
    Update an existing record in the in-memory dataframe or append a new one.

    This function always persists the resulting dataframe to the CSV file
    path stored in `current_app.db['path']` (if present). The `persist`
    parameter is accepted for backward compatibility but ignored.

    Matching order for update: 'unique_id', '_id', 'created_at' (first match wins).
    If no matching row is found the record is appended.
    """
    cfg = current_app.db
    df = cfg.get("dataframe")
    if df is None or df.empty:
        print("❌ No dataframe available to update data")
        return False
    
    if match_column not in df.columns:
        print(f"❌ Match column '{match_column}' not in dataframe columns")
        return False

    match_index = df.index[df[match_column] == match_value].tolist()
    if not match_index:
        print(f"❌ No matching record found for {match_column} = {match_value}")
        return False
    
    match_index = match_index[0]  # take first match

    for k, v in data.items():
        if k not in df.columns:
            df[k] = ""  # add new column with default empty values
        df.at[match_index, k] = v
        
    df.at[match_index, "updated_at"] = datetime.utcnow().isoformat()

    cfg["dataframe"] = df

    csv_path = cfg.get("path")
    if csv_path:
        try:
            csv_dir = os.path.dirname(os.fspath(csv_path))
            if csv_dir:
                os.makedirs(csv_dir, exist_ok=True)
            df.to_csv(csv_path, index=False)
        except Exception:
            print("❌ Failed to write to CSV file")
            return False

    return True