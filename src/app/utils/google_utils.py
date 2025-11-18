import json
from datetime import datetime
from typing import Any, Dict, List, Union
import gspread
from gspread.utils import rowcol_to_a1
import numpy as np

def append_record(sheet: gspread.Worksheet, headers: List[str], data: Dict[str, Any]) -> List[Any]:
    """
    Append a new record (row) to the worksheet using the provided header order.

    Args:
        sheet: Target worksheet.
        headers: Column headers defining the order.
        data: Data dictionary to append.
    """
    row = _build_row(headers, data)
    sheet.append_row(row, value_input_option="USER_ENTERED")
    return row

def update_record(
    sheet: gspread.Worksheet,
    headers: List[str],
    match_column: Union[str, List[str]],
    match_value: Union[Any, List[Any]],
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
    headers = headers
    header_map = _header_map(headers)

    # normalize match_column and match_value to lists
    if isinstance(match_column, str):
        match_columns = [match_column]
    else:
        match_columns = list(match_column)

    if not isinstance(match_value, list):
        match_values = [match_value]
    else:
        match_values = list(match_value)

    if len(match_columns) != len(match_values):
        raise ValueError("match_column and match_value must have the same length")

    # resolve target headers for each requested match column
    target_headers: List[str] = []
    for mc in match_columns:
        th = header_map.get(mc.lower())
        if th is None:
            raise ValueError(f"Column '{mc}' does not exist in the Google Sheet.")
        target_headers.append(th)

    values = sheet.get_all_values()
    if len(values) <= 1:
        return False

    # iterate rows and find the first row where all target columns match the corresponding values
    for row_offset, row in enumerate(values[1:], start=2):
        all_match = True
        for th, mv in zip(target_headers, match_values):
            col_index = headers.index(th)
            cell_value = row[col_index] if col_index < len(row) else ""

            # treat empty/None match value as matching empty cells
            if mv is None or str(mv).strip() == "":
                if str(cell_value).strip() != "":
                    all_match = False
                    break
            else:
                if _normalize_string(cell_value) != _normalize_string(mv):
                    all_match = False
                    break

        if not all_match:
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
    match_column: Union[str, List[str]],
    match_value: Union[Any, List[Any]],
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
    headers = headers
    header_map = _header_map(headers)

    # normalize match_column and match_value to lists
    if isinstance(match_column, str):
        match_columns = [match_column]
    else:
        match_columns = list(match_column)

    if not isinstance(match_value, list):
        match_values = [match_value]
    else:
        match_values = list(match_value)

    if len(match_columns) != len(match_values):
        raise ValueError("match_column and match_value must have the same length")

    # resolve target headers for each requested match column
    target_headers: List[str] = []
    for mc in match_columns:
        th = header_map.get(mc.lower())
        if th is None:
            raise ValueError(f"Column '{mc}' does not exist in the Google Sheet.")
        target_headers.append(th)

    values = sheet.get_all_values()
    if len(values) <= 1:
        return []

    matches: List[Dict[str, Any]] = []

    for row in values[1:]:
        all_match = True
        for th, mv in zip(target_headers, match_values):
            col_index = headers.index(th)
            cell_value = row[col_index] if col_index < len(row) else ""

            # treat empty/None match value as matching empty cells
            if mv is None or str(mv).strip() == "":
                if str(cell_value).strip() != "":
                    all_match = False
                    break
            else:
                if _normalize_string(cell_value) != _normalize_string(mv):
                    all_match = False
                    break

        if all_match:
            matches.append(_row_to_dict(headers, row))

    return matches


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
