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



REQUIRED_COLS = [
    "Form_ID","Full_Name","Email","Phone_Number","PR_Status",
    "PR_Card_Number","PR_File_Upload_URLs","Amount_of_Payment",
    "Payer_Full_Name","Zeffy_Unique_ID","Paid"
]

def save_to_csv(record: dict) -> bool:
    """
    Append a single record to the CSV file defined in current_app.db['path'].
    Writes a header if the file is new or empty. Returns True after writing.
    """
    cfg = current_app.db
    path = os.fspath(cfg["path"])  # Path object -> str

    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_or_empty = (not os.path.exists(path)) or os.path.getsize(path) == 0

    rec = dict(record)
    rec.setdefault("created_at", datetime.utcnow().isoformat())
    for col in REQUIRED_COLS:
        rec.setdefault(col, "")

    abs_path = os.path.abspath(path)
    print(f"[save_to_csv] writing to: {abs_path}")

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLS, extrasaction="ignore")
        if new_or_empty:
            print("[save_to_csv] writing header")
            writer.writeheader()
        writer.writerow(rec)
        print("[save_to_csv] wrote 1 row")

    return True



def update_to_csv(record: dict) -> bool:
    """
    Update a record by Email (case-insensitive). Returns True if updated.
    """
    csv_cfg = current_app.db
    csv_path = csv_cfg["path"]
    df = _load_df(csv_path)

    if "Email" not in record:
        raise ValueError("Email is required to update CSV")

    if "Email" not in df.columns or df.empty:
        return False

    mask = _lower_series(df["Email"]) == str(record["Email"]).strip().lower()
    if not mask.any():
        return False

    # Update only provided keys to avoid clobbering
    for k, v in record.items():
        if k in df.columns:
            df.loc[mask, k] = v
        else:
            # add new column if needed
            df[k] = pd.Series(dtype="object")
            df.loc[mask, k] = v

    df.to_csv(csv_path, index=False)
    return True
