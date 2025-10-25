from flask import current_app
from datetime import datetime
import pandas as pd
from datetime import datetime
import os

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

    match_index = df.index[df[match_column] == match_value].tolist()

    if not match_index:
        print(f"❌ No matching record found for {match_column} = {match_value}")
        return False
    
    match_index = match_index[0]  # take first match

    for k, v in data.items():
        if k in df.columns:
            df.at[match_index, k] = v

    df.at[match_index, "updated_at"] = datetime.utcnow().isoformat()

    try:
        csv_dir = os.path.dirname(os.fspath(csv_path))
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)
        df.to_csv(csv_path, index=False)
    except Exception as e:
        print(f"❌ Failed to write to CSV file: {e}")
        return False
    
    return True

# File: database_utils.py (Add this function)

def update_pr_status(registration_id: str, data: dict) -> bool:
    """
    Updates the PR verification status and details in the CSV store.
    This function wraps update_to_csv, matching by registration_id.

    Args:
        registration_id (str): The unique ID of the record to match.
        data (dict): The fields (like pr_status, message) to update.

    Returns:
        bool: True on success.
    """
    # The registration_id must be matched against a column containing the ID (e.g., 'Form_ID' or 'registration_id')
    # For this function to work correctly, your CSV must have a column named 'registration_id'
    
    # We pass the update task to the general update function
    return update_to_csv(
        data=data, 
        match_column="registration_id", 
        match_value=registration_id
    )