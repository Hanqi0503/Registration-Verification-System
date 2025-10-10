
# Registration-Verification-System

Lightweight Flask-based backend for handling registration + payment verification workflows.

This repository provides a small MVC-style Flask application with:
- environment-based configuration (python-dotenv)
- a CSV-backed datastore for local development (and optional MongoDB support)
- background job that checks payment notification emails using an interval scheduler
- modular structure (routes, services, background jobs, utils)

## System Flowchart

![System Flowchart](png/Phase2-Flowchart.png)


## Quick overview

- Project root: contains `pyproject.toml`, `.env.example`, and this `README.md`.
- Application package: `src/app/` (contains config, routes, services, background jobs).
- Entrypoint: `src/main.py` (creates/starts the Flask app).

## Recommended Python

Use Python 3.9 (the codebase uses modern type union syntax and other features). 

## Layout (important files)

```
Registration-Verification-System/
├── .env.example              # example env with placeholders
├── pyproject.toml
├── src/
│   ├── main.py               # application entrypoint
│   └── app/
│       ├── __init__.py       # create_app factory
│       ├── config/config.py  # Config class that loads .env via python-dotenv
│       ├── routes/           # Flask blueprints (registration, payment)
│       ├── services/         # business logic + db helpers
│       └── background/       # scheduler jobs (payment_watcher)
└── data/
	└── registration_data.csv # CSV store (created/loaded automatically)
```

## Setup (local development)

1. Clone the repo and cd into it.

2. Quick run with `uv` (fast, minimal) (Ignore this step if you choose run step 3)

If you prefer a very short workflow and already have the `uv` runner available on your machine, you can use it to sync environment and run the app quickly:

```bash
# sync dependencies / environment (if your uv setup supports it)
uv sync
```

Note: `uv` is optional — if you don't have it or prefer a more explicit setup, use one of the normal workflows below.

3. Standard workflows (recommended) (Ignore this step if you choose run step 2)

- Create and activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

- Install dependencies.

If you use Poetry (project has `pyproject.toml`):

```bash
poetry install
poetry shell
```

Or with pip (if you maintain a `requirements.txt`) you can do:

```bash
# optional: create requirements.txt from poetry if needed
pip install -r requirements.txt
```

4. Copy and fill the environment file:

```bash
cp .env.example .env
# then edit .env and set real secrets (do NOT commit .env)
```

The code loads `.env` from the repository root using python-dotenv. The `Config` class in `src/app/config/config.py` exposes those env values as attributes.

## Running the app

Run directly with Python (recommended during development):

```bash
python src/main.py
```

If you use the `uv` runner you previously used:

```bash
uv run python src/main.py
```

Visit http://127.0.0.1:5050 (or the host/port from your `.env`) to see the landing endpoint.

## Configuration

- Edit `.env` (copy from `.env.example`) and fill required values: MongoDB creds (if used), AWS/S3 keys (if used), admin email, and scheduler interval `CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES`.
- `src/app/config/config.py` provides a `Config` class that reads env vars and offers `Config.validate_required()` to fail fast on missing required keys.

Notes:
- `CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES` must be an integer; the background scheduler expects a numeric minutes value.
- If you see errors about saving CSV files to a non-existent `data` directory, either create the directory or let the `init_csv` helper create it for you. The repository already contains a `data/registration_data.csv` example.

Additional configuration variables
- `JOTFORM_API_KEY` - (optional) API key used when fetching image URLs hosted by JotForm. When present the utility will append it as `?apiKey=...` to JotForm URLs.
- `NINJA_API_URL` - (optional) Image->text OCR endpoint used by the `ninja_image_to_text` helper (default: `https://api.api-ninjas.com/v1/imagetotext`).
- `NINJA_API_KEY` - (optional but required if you call the Ninja OCR service) API key for the Image->Text API (api-ninjas.com).

## Data storage

- Local development doubles as a CSV-backed datastore in `data/registration_data.csv` (managed by `app.services.database.init_csv`). The service resolves that path relative to the project root so running from other working directories still works.
- For production or scalable scenarios, the app can use MongoDB (`pymongo`) — credentials are loaded from env and the `init_mongoDB` helper shows how to construct the client.

## Background jobs

- The payment watcher uses APScheduler to poll email notifications (see `src/app/background/payment_watcher.py`). Configure the interval via `CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES` in `.env`.

## Routes

All application routes are registered under the `/api` prefix. The main endpoints are:

- POST /api/jotform-webhook
	- Description: Receives JotForm webhook submissions. Expects JSON body from JotForm.
	- Query params (required): `pr_amount` (float), `normal_amount` (float)
	- Returns: JSON with `message` and `result` (processed registration details).
	- Example:

```bash
curl -X POST "http://127.0.0.1:5050/api/jotform-webhook?pr_amount=150&normal_amount=100" \
	-H "Content-Type: application/json" \
	-d '{"name": {"first": "Jane", "last": "Doe"}, "email": "jane@example.com", ... }'
```

- GET /api/check-payments
	- Description: Triggers a one-time scan for payment emails and returns matched results.
	- Query params (optional):
	  - `from` (email address, defaults to `ZEFFY_EMAIL` from config)
	  - `subject` (defaults to `ZEFFY_SUBJECT`)
	  - `since` (ISO date string `YYYY-MM-DD`) — if provided, only emails on/after this date will be processed.
	- Returns: JSON with `count` and `results`.
	- Example:

```bash
curl "http://127.0.0.1:5050/api/check-payments?from=no-reply%40gmail.com&subject=Payment+Received&since=2025-10-01"
```

Notes:
- The Blueprints are registered in `src/app/routes/__init__.py` and mounted at `/api`.
- Handlers return JSON and appropriate HTTP status codes for error cases.

## Image utilities & OCR

This project includes small helpers for downloading images and performing OCR using an external "image to text" API. They live under `src/app/utils/image_utils.py` and the main helpers are:

- `fetch_image_bytes(image_url: str) -> bytes`
	- Downloads an image from `image_url` and returns the raw bytes.
	- If the URL points to an HTML page, the helper will parse the page and extract the first `<img src=...>` it finds and then download that image instead.
	- If `JOTFORM_API_KEY` is set in your `.env`, the function will append it as a query parameter when requesting JotForm-hosted image URLs.

- `extract_image_url(html_content: str | bytes) -> str`
	- Parses HTML content and returns the first `<img>` `src` value found. Raises `ValueError` if none found.

- `ninja_image_to_text(img_url: str) -> dict`
	- Convenience wrapper that downloads image bytes (via `fetch_image_bytes`) then calls the configured `NINJA_API_URL` with header `X-Api-Key: <NINJA_API_KEY>` and returns the parsed JSON result.
	- Requires `NINJA_API_KEY` set in `.env` when you call it.

Example usage (Python):

```python
from app.utils.image_utils import fetch_image_bytes, ninja_image_to_text

# download raw bytes
img_bytes = fetch_image_bytes('https://example.com/path/to/image.jpg')

# send image to OCR service
ocr_result = ninja_image_to_text('https://example.com/path/to/image.jpg')
print(ocr_result)
```

Dependencies
- These helpers use the following third-party packages; ensure they are installed in your environment (they are listed in `pyproject.toml`):
	- `requests` (HTTP requests)
	- `beautifulsoup4` (HTML parsing, provides `bs4`)
	- `pillow` (PIL, for fallback image decoding)


## Development tips & common troubleshooting

- Python version: Use 3.9.
- Missing `data` directory: create it or ensure `init_csv` runs (it attempts to create the parent path if needed).
- Ensure `.env` is present in the project root when running locally. Use `.env.example` as a template.

## Git / secrets

- This project includes a `.gitignore` which contains `.env` and local virtual environment directories. Do NOT commit `.env`.
- Keep a cleaned `.env.example` in the repo with placeholder values so teammates know required keys.

## Contributing

1. Create a branch: `git checkout -b feat/your-change`
2. Commit and push, then open a PR wait for approve.

