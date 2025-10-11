from flask import current_app
from datetime import datetime

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
    Save a record to a CSV file.

    Args:
        data (dict): The data to be saved.

    Returns:
        Boolean
    """
    return True
    # Assigned to Jay
    # Please implement the CSV saving logic here
    # Please using current_app.db because app.db = init_csv() in app.__init__.py
    # So you can check the logic in init_csv() function in app.services.database
        

def update_to_csv(data: dict) -> bool:
    """
    Update a record to a CSV file.

     Args:
        data (dict): The data to be saved.

    Returns:
        Boolean
    """
    return True

    # Assigned to Jay
    # Please implement the CSV saving logic here
    # Please using current_app.db because app.db = init_csv() in app.__init__.py
    # So you can check the logic in init_csv() function in app.services.database