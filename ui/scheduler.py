from apscheduler.schedulers.background import BackgroundScheduler
from typing import Callable, Dict, Any

_scheduler = None

def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler

def schedule_callable(func: Callable, trigger: Dict[str, Any]) -> str:
    sch = start_scheduler()
    job = sch.add_job(func, trigger=trigger.get("type", "interval"), **{k:v for k,v in trigger.items() if k!="type"})
    return job.id

