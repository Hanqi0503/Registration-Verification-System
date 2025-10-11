from apscheduler.schedulers.background import BackgroundScheduler
from app.services import payment_service
from app.config.config import Config
from datetime import datetime, timezone
def start_payment_job():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: payment_service(Config.ZEFFY_EMAIL, Config.ZEFFY_SUBJECT, datetime.now(timezone.utc).date()),
        trigger="interval",
        minutes=int(Config.CHECK_ZEFFY_EMAIL_TIME_BY_MINUTES),
        id="payment_checker",
        replace_existing=True,
    )
    scheduler.start()