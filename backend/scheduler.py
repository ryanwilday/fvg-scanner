from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone

scheduler = BackgroundScheduler(timezone="UTC")

# Maps timeframe string to (minute, hour) cron fields
TIMEFRAME_CRON = {
    "1m":  {"minute": "*"},
    "5m":  {"minute": "0,5,10,15,20,25,30,35,40,45,50,55"},
    "15m": {"minute": "0,15,30,45"},
    "1h":  {"minute": "0"},
    "4h":  {"minute": "0", "hour": "0,4,8,12,16,20"},
    "6h":  {"minute": "0", "hour": "0,6,12,18"},
    "1d":  {"minute": "0", "hour": "0"},
    "1w":  {"minute": "0", "hour": "0", "day_of_week": "mon"},
}

_registered_jobs: dict[str, str] = {}  # timeframe -> job_id


def register_timeframe(timeframe: str, scan_fn):
    """Register a cron job for the given timeframe if not already registered."""
    if timeframe in _registered_jobs:
        return

    cron_kwargs = TIMEFRAME_CRON.get(timeframe)
    if not cron_kwargs:
        print(f"[scheduler] Unknown timeframe: {timeframe}")
        return

    job_id = f"scan_{timeframe}"
    scheduler.add_job(
        scan_fn,
        CronTrigger(**cron_kwargs, timezone="UTC"),
        id=job_id,
        replace_existing=True,
        args=[timeframe],
    )
    _registered_jobs[timeframe] = job_id
    print(f"[scheduler] Registered job for timeframe={timeframe}")


def unregister_timeframe(timeframe: str):
    job_id = _registered_jobs.pop(timeframe, None)
    if job_id and scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def start():
    if not scheduler.running:
        scheduler.start()


def shutdown():
    if scheduler.running:
        scheduler.shutdown()
