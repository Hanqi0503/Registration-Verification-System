from pymongo import MongoClient
import pandas as pd
from pathlib import Path
from app.config.config import Config
from typing import Optional
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
