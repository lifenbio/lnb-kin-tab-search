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
        # 14시 → 19시 변경: 0시 cron 이 ~18시30~42분에 끝나는 패턴이라 14시 발사 시 부분 데이터.
        # 19시면 마진 충분, 운영 4명에게 완전 데이터 메일 1통.
        "schedule": crontab(minute=00, hour='19', day_of_week='mon-sun')
    }
}
