from flask import current_app
from datetime import datetime
import pandas as pd
from datetime import datetime
import os
import json
import numpy as np

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

def add_to_csv(data: dict) -> bool:
    """
    Append a single record to the CSV file defined in current_app.db['path'].

    Args:
        data (dict): The data to be saved.

    Returns:
        bool: True on success.
    """
    cfg = current_app.db
    print(f"Current DB config: {cfg}")
    csv_path = cfg.get("path")

    if not csv_path or not os.path.exists(os.fspath(csv_path)):
        print("❌ CSV path missing or file does not exist")
        return False 

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Failed to read CSV file: {e}")
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

    new_row = pd.DataFrame([rec], columns=df.columns)
    df = pd.concat([df, new_row], ignore_index=True)

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
    Update or append a record in the CSV backing store.

    Args:
        data (dict): Fields to update or insert.
        match_column (str): Column name to match (case-insensitive).
        match_value: Value to match in the match_column.

    Returns:
        bool: True on success, False on missing CSV path or I/O errors.
    """
    cfg = current_app.db
    csv_path = cfg.get("path")
    if not csv_path or not os.path.exists(os.fspath(csv_path)):
        print("❌ CSV path missing or file does not exist")
        return False

    # Load the latest dataframe from disk
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Failed to read CSV file: {e}")
        return False

    match_index = df.index[df[match_column].astype(str).str.lower().str.strip() == str(match_value).lower().strip()].tolist()

    if not match_index:
        print(f"❌ No matching record found for {match_column} = {match_value}")
        return False
    
    match_index = match_index[0]  # take first match

    for k, v in data.items():
        # normalize iterables/dicts to a scalar for CSV
        if isinstance(v, (list, tuple, dict, np.ndarray)):
            v = json.dumps(v)

        # convert column to object to avoid dtype incompatibility warnings/errors
        if not pd.api.types.is_object_dtype(df[k].dtype):
            df[k] = df[k].astype(object)

        # finally assign single scalar value
        df.at[match_index, k] = v

    # ensure updated_at exists and is set (object dtype)
    if "Updated_At" not in df.columns:
        df["Updated_At"] = ""
    if not pd.api.types.is_object_dtype(df["Updated_At"].dtype):
        df["Updated_At"] = df["Updated_At"].astype(object)
    df.at[match_index, "Updated_At"] = datetime.utcnow().isoformat()

    try:
        csv_dir = os.path.dirname(os.fspath(csv_path))
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)
        df.to_csv(csv_path, index=False)
    except Exception as e:
        print(f"❌ Failed to write to CSV file: {e}")
        return False
    
    return True

def get_from_csv(match_column: str, match_value):
    """
    Retrieve a record from the CSV backing store.

    Args:
        match_column (str): Column name to match (case-insensitive).
        match_value: Value to match in the match_column.

    Returns:
        dict | None: The matching record as a dictionary, or None if not found.
    """
    cfg = current_app.db
    csv_path = cfg.get("path")
    if not csv_path or not os.path.exists(os.fspath(csv_path)):
        print("❌ CSV path missing or file does not exist")
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Failed to read CSV file: {e}")
        return None

    match_rows = df[df[match_column].astype(str).str.lower().str.strip() == str(match_value).lower().strip()]

    if match_rows.empty:
        print(f"❌ No matching record found for {match_column} = {match_value}")
        return None

    return match_rows.to_dict(orient='records')