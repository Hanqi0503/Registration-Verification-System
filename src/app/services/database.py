from flask import json
from pymongo import MongoClient
import pandas as pd
from pathlib import Path
from typing import Optional
from google.oauth2.service_account import Credentials
import gspread

from app.config.config import Config

def init_mongoDB():
    """
    Initialize MongoDB connection and return the database instance.
    
    Args:
        None

    Returns:
        db: MongoDB database instance.
    """
    client = MongoClient(
        f"mongodb+srv://{Config.MONGO_USERNAME}:{Config.MONGO_PASSWORD}@{Config.MONGO_CLUSTER}/?retryWrites=true&w=majority"
    )
    db = client["webhook_db"]
    collection = db["webhook_data"]
    collection.create_index({"created_at": 1}, expireAfterSeconds=2592000)
    print("✅ MongoDB connected")
    return db


def init_csv(file_path: Optional[str] = None):
    """
    Load or create a CSV-based data store.

    Args:
        file_path (str): Path to the CSV file.
    Returns:
        dict: Contains the file path and the loaded DataFrame.
    """
    # project root is two parents above this file: src/app/services -> src/app -> src -> project root
    project_root = Path(__file__).resolve().parents[2]

    if file_path:
        p = Path(file_path)
        path = p if p.is_absolute() else (project_root / p)
    else:
        path = project_root / "data" / "registration_data.csv"

    # ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if not path.exists():
        # Create an empty DataFrame with default columns
        df = pd.DataFrame(columns=["created_at", "content"])
        df.to_csv(path, index=False)
        print(f"🆕 Created new CSV file at {path}")
    else:
        df = pd.read_csv(path)
        print(f"✅ Loaded existing CSV file from {path}")

    return {"path": path}


def init_google_sheet(file_path: Optional[str] = None):
    """
    Initialize Google Sheet connection details for use throughout the app.
    Args:
        file_path (str): Path to the google sheet credential json file.
    Returns:
        dict: Contains the authorized client, worksheet, and cached headers.
    """
    spreadsheet_id = Config.GOOGLE_SPREADSHEET_ID
    worksheet_name = Config.GOOGLE_WORKSHEET_NAME

    if not spreadsheet_id:
        raise RuntimeError("GOOGLE_SPREADSHEET_ID is not configured.")

    project_root = Path(__file__).resolve().parents[2]

    if file_path:
        p = Path(file_path)
        path = p if p.is_absolute() else (project_root / p)
    else:
        path = project_root /"data" / "key" /"credentials.json"

    info = json.loads(path.read_text())

    credentials = Credentials.from_service_account_info(info, scopes=("https://www.googleapis.com/auth/spreadsheets",))
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    headers = [h.strip() for h in worksheet.row_values(1)]
    if not headers:
        raise RuntimeError("The Google Sheet must contain a header row in the first row.")

    return {"client": client, "sheet": worksheet, "headers": headers}
