import os
import sys
import os
import sys
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
from app.config.config import Config
from app.services import payment_service
from app.services.reminder_service import reminder_nonpaid_email

_scheduler = BackgroundScheduler()
_job_id_payment = "payment_checker"
_job_id_reminder = "reminder_nonpaid"


def _payment_job(app):
    with app.app_context():
        print(f"[payment_watcher] payment job PID={os.getpid()} at {datetime.now(timezone.utc).isoformat()}")
        payment_service(Config.ZEFFY_EMAIL, Config.ZEFFY_SUBJECT, (datetime.now(timezone.utc) - timedelta(days=1)).date())

def _reminder_job(app):
    with app.app_context():
        print(f"[payment_watcher] reminder job PID={os.getpid()} at {datetime.now(timezone.utc).isoformat()}")
        reminder_nonpaid_email()


def start_payment_job(app):
    # avoid starting in parent reloader or in multi-worker environments
    if Config.FLASK_DEBUG:
        return
    if _scheduler.get_job(_job_id_payment) is None:
        _scheduler.add_job(func=lambda: _payment_job(app),
                           trigger="interval",
                           minutes=int(Config.CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES),
                           id=_job_id_payment,
                           replace_existing=True)
    if _scheduler.get_job(_job_id_reminder) is None:
        # use CONFIG value REMINDER_INTERVAL_MINUTES if available, else reuse CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES
        rem_min = int(getattr(Config, "REMINDER_INTERVAL_MINUTES", Config.CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES))
        _scheduler.add_job(func=lambda: _reminder_job(app),
                           trigger="interval",
                           minutes=rem_min,
                           id=_job_id_reminder,
                           replace_existing=True)

    if not _scheduler.running:
        _scheduler.start()
        print(f"[payment_watcher] scheduler started in PID={os.getpid()}")