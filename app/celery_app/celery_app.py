from datetime import timedelta

from celery import Celery


celery_app = Celery(
    "delete_expired_token",
    broker="redis://localhost:6379/0",
)


celery_app.conf.beat_schedule = {
    "every_day_delete_expired_token": {
        "task": "tasks.delete_expired_token_task",
        "schedule": timedelta(days=1),
    }
}