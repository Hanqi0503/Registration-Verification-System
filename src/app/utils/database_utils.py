from typing import Any, Dict, List, Optional, Tuple

from flask import current_app

from app.utils import google_utils


def _get_sheet_context() -> Tuple[Optional[Any], Optional[List[str]], Optional[Dict[str, Any]]]:
    cfg = getattr(current_app, "db", None)
    if not cfg:
        print("❌ Google Sheet configuration missing from Flask application context")
        return None, None, None

    sheet = cfg.get("sheet")
    if sheet is None:
        print("❌ Google Sheet worksheet handle is not initialized")
        return None, None, cfg

    headers = cfg.get("headers")
    if not headers:
        google_utils.refresh_headers(cfg)
        headers = cfg.get("headers")

    if not headers:
        print("❌ Google Sheet header row is empty or missing")
        return None, None, cfg

    return sheet, headers, cfg


def add_to_csv(data: Dict[str, Any]) -> bool:
    """
    Append a single record to the configured Google Sheet.

    Retains the original function name for backwards compatibility with existing callers.
    """
    sheet, headers, _ = _get_sheet_context()
    if sheet is None or headers is None:
        return False

    try:
        google_utils.append_record(sheet, headers, data)
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"❌ Failed to append data to Google Sheet: {exc}")
        return False


def update_to_csv(data: Dict[str, Any], match_column: str, match_value: Any) -> bool:
    """
    Update a Google Sheet row matching the provided column/value pair.
    """
    sheet, headers, cfg = _get_sheet_context()
    if sheet is None or headers is None:
        return False

    try:
        updated = google_utils.update_record(sheet, headers, match_column, match_value, data)
        if not updated:
            print(f"❌ No matching record found for {match_column} = {match_value}")
            return False

        google_utils.refresh_headers(cfg)  # type: ignore[arg-type]
        return True
    except ValueError as exc:
        print(f"❌ {exc}")
        return False
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"❌ Failed to update Google Sheet record: {exc}")
        return False


def get_from_csv(match_column: str, match_value: Any) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve row(s) from the Google Sheet matching the provided column/value pair.
    """
    sheet, headers, _ = _get_sheet_context()
    if sheet is None or headers is None:
        return None

    try:
        rows = google_utils.find_records(sheet, headers, match_column, match_value)
    except ValueError as exc:
        print(f"❌ {exc}")
        return None
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"❌ Failed to query Google Sheet: {exc}")
        return None

    if not rows:
        print(f"❌ No matching record found for {match_column} = {match_value}")
        return None

    return rows
