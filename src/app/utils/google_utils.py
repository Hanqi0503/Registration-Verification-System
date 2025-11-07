import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is an optional dependency at runtime
    np = None  # type: ignore

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


def load_credentials(
    credentials_file: Optional[str] = None,
    credentials_json: Optional[str] = None,
) -> Credentials:
    """
    Construct Google service account credentials either from a JSON file or raw JSON string.

    Args:
        credentials_file: Path to the credentials JSON file.
        credentials_json: Raw JSON string containing credentials.

    Returns:
        Credentials: Authorized service account credentials.
    """
    if credentials_json:
        info = json.loads(credentials_json)
        return Credentials.from_service_account_info(info, scopes=_SCOPES)

    if credentials_file:
        return Credentials.from_service_account_file(credentials_file, scopes=_SCOPES)

    raise RuntimeError(
        "Google service account credentials are not configured. "
        "Provide GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON."
    )


def init_sheet(
    spreadsheet_id: str,
    worksheet_name: Optional[str] = None,
    credentials_file: Optional[str] = None,
    credentials_json: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Initialize a Google Sheet client and return useful handles.

    Args:
        spreadsheet_id: Target Google Spreadsheet ID.
        worksheet_name: Specific worksheet/tab name (defaults to the first sheet).
        credentials_file: Path to the service account JSON file.
        credentials_json: Raw JSON string for the service account.
        ''
    Returns:
        dict: Dictionary containing the authorized client, worksheet, and header list.
    """
    credentials = load_credentials(credentials_file, credentials_json)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    headers = fetch_headers(worksheet)
    if not headers:
        raise RuntimeError("The Google Sheet must contain a header row in the first row.")

    return {"client": client, "sheet": worksheet, "headers": headers}


def fetch_headers(sheet: gspread.Worksheet) -> List[str]:
    """Return the header row (first row) as a list."""
    return [h.strip() for h in sheet.row_values(1)]


def append_record(sheet: gspread.Worksheet, headers: List[str], data: Dict[str, Any]) -> None:
    """
    Append a new record (row) to the worksheet using the provided header order.

    Args:
        sheet: Target worksheet.
        headers: Column headers defining the order.
        data: Data dictionary to append.
    """
    row = _build_row(headers, data)
    sheet.append_row(row, value_input_option="USER_ENTERED")


def update_record(
    sheet: gspread.Worksheet,
    headers: List[str],
    match_column: str,
    match_value: Any,
    data: Dict[str, Any],
) -> bool:
    """
    Update the first row that matches match_value in match_column.

    Args:
        sheet: Target worksheet.
        headers: Column headers defining the order.
        match_column: Header (case-insensitive) used to locate the row.
        match_value: Value to match (case-insensitive, trimmed).
        data: Values to merge into the matched row.

    Returns:
        bool: True when an update occurs, False when no matching row is found.
    """
    headers = headers or fetch_headers(sheet)
    header_map = _header_map(headers)
    target_header = header_map.get(match_column.lower())

    if target_header is None:
        raise ValueError(f"Column '{match_column}' does not exist in the Google Sheet.")

    values = sheet.get_all_values()
    if len(values) <= 1:
        return False

    col_index = headers.index(target_header)
    normalized_match = _normalize_string(match_value)

    for row_offset, row in enumerate(values[1:], start=2):
        cell_value = row[col_index] if col_index < len(row) else ""
        if _normalize_string(cell_value) != normalized_match:
            continue

        existing = _row_to_dict(headers, row)
        for key, value in data.items():
            header_key = header_map.get(key.lower())
            if not header_key:
                continue  # mimic CSV behavior: ignore keys that don't correspond to headers
            existing[header_key] = _serialize_value(value)

        updated_at_header = header_map.get("updated_at")
        if updated_at_header:
            existing[updated_at_header] = datetime.utcnow().isoformat()

        start = rowcol_to_a1(row_offset, 1)
        end = rowcol_to_a1(row_offset, len(headers))
        new_row = _build_row(headers, existing)
        sheet.update(f"{start}:{end}", [new_row], value_input_option="USER_ENTERED")
        return True

    return False


def find_records(
    sheet: gspread.Worksheet,
    headers: List[str],
    match_column: str,
    match_value: Any,
) -> List[Dict[str, Any]]:
    """
    Retrieve all rows matching the given value in the specified column.

    Args:
        sheet: Target worksheet.
        headers: Column headers defining the order.
        match_column: Header (case-insensitive) used to filter rows.
        match_value: Target value (case-insensitive, trimmed).

    Returns:
        list[dict]: Matching rows converted into dictionaries.
    """
    headers = headers or fetch_headers(sheet)
    header_map = _header_map(headers)
    target_header = header_map.get(match_column.lower())
    if target_header is None:
        raise ValueError(f"Column '{match_column}' does not exist in the Google Sheet.")

    values = sheet.get_all_values()
    if len(values) <= 1:
        return []

    col_index = headers.index(target_header)
    normalized_match = _normalize_string(match_value)
    matches: List[Dict[str, Any]] = []

    for row in values[1:]:
        cell_value = row[col_index] if col_index < len(row) else ""
        if _normalize_string(cell_value) == normalized_match:
            matches.append(_row_to_dict(headers, row))

    return matches


def refresh_headers(cfg: Dict[str, Any]) -> None:
    """
    Refresh the cached header list from the worksheet and update the config dict in-place.

    Args:
        cfg: Dictionary containing at least a 'sheet' entry.
    """
    sheet = cfg.get("sheet")
    if sheet:
        cfg["headers"] = fetch_headers(sheet)


def _header_map(headers: List[str]) -> Dict[str, str]:
    return {header.lower(): header for header in headers}


def _row_to_dict(headers: List[str], row: List[Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for index, header in enumerate(headers):
        result[header] = row[index] if index < len(row) else ""
    return result


def _build_row(headers: List[str], data: Dict[str, Any]) -> List[Any]:
    row: List[Any] = []
    for header in headers:
        default = datetime.utcnow().isoformat() if header.lower() == "created_at" else ""
        value = _resolve_value(header, data, default)
        row.append(_serialize_value(value))
    return row


def _resolve_value(header: str, data: Dict[str, Any], default: Any) -> Any:
    if header in data:
        return data[header]

    lowered = header.lower()
    if lowered in data:
        return data[lowered]

    return default


def _serialize_value(value: Any) -> Any:
    if value is None:
        return ""

    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value)

    if np is not None and isinstance(value, np.ndarray):  # type: ignore[attr-defined]
        return json.dumps(value.tolist())

    return value


def _normalize_string(value: Any) -> str:
    return str(value).strip().lower()
