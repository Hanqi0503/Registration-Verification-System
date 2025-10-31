import sys
from pathlib import Path

# Ensure the repository 'src' directory is on sys.path so tests can import `app`.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
