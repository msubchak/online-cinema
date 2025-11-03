from celery import Celery

celery_app = Celery(
    "delete_expired_token",
    broker="redis://redis:6379/0",
)

celery_app.autodiscover_tasks(["app.celery_app"])
