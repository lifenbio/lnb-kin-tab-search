"""Celery 정시 태스크 wrapper.

본체 로직은 ``common.services.naver_in`` 에 있다. 이 파일은 Celery 가 인식하는
``@shared_task`` 진입점만 유지한다. 일별 산출물 (메일·엑셀·DailyResult row) 의
스펙은 서비스 모듈이 보장한다.
"""

from datetime import datetime, timezone

from celery import shared_task

from common.services import naver_in


@shared_task
def naver_in_daily_collection():
    return naver_in.collect_daily_kin()


@shared_task
def naver_in_daily_collection_create_excel():
    return naver_in.build_daily_excel(datetime.now(timezone.utc).date())


@shared_task
def naver_in_detail_view_collection():
    return naver_in.collect_detail_view()
