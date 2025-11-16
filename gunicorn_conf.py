import os
import sys
import traceback

# Ensure the src directory is on sys.path so "import app" works
ROOT = os.path.abspath(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from app import create_app
from app.background.payment_watcher import start_payment_job

def when_ready(server):
    """
    Gunicorn hook executed in the master process when the server is ready.
    Start the scheduler here so it runs once (in master), not in workers.
    """
    try:
        app = create_app()
        start_payment_job(app)
        server.log.info("Started scheduler from gunicorn master process")
    except Exception:
        server.log.error("Failed to start scheduler in master process:\n" + traceback.format_exc())
