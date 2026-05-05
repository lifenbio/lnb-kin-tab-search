import os
from celery import Celery
from celery.schedules import crontab


"""
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "main.settings.dev",
)
"""
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "main.settings.prod",
)

app = Celery('main')

app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)

app.autodiscover_tasks()
app.conf.timezone = 'Asia/Seoul'

app.conf.beat_schedule = {
    "naver-in-detail-view-collection": {
        "task": "common.tasks.naver_in_detail_view_collection",
        "schedule": crontab(minute=00, hour='21', day_of_week='mon-sun')
    },
    "naver-in-daily-collection-job": {
        "task": "common.tasks.naver_in_daily_collection",
        "schedule": crontab(minute=00, hour='00', day_of_week='mon-sun')
    },
    "naver-in-daily-collection-create-excel": {
        "task": "common.tasks.naver_in_daily_collection_create_excel",
        "schedule": crontab(minute=00, hour='14', day_of_week='mon-sun')
    }
}
