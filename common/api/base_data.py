"""기준정보 업로드 + 디버그 트리거 엔드포인트.

업로드 엔드포인트 (``/keyword``, ``/url``, ``/new/url``) 는 운영 데이터 입력 경로.

``/test-*`` 엔드포인트는 운영 cron 외에 수동 검증/디버그용 트리거. 본체 로직은
``common.services.naver_in`` 의 동일 함수를 호출 — Celery 태스크 (``common.tasks``)
와 같은 결과를 만든다. 무거운 수집 작업은 동기 호출이 HTTP 타임아웃을 일으키므로
Celery 큐로 enqueue 한다.
"""

from datetime import datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup
from ninja import Router, File
from ninja.files import UploadedFile

from common.models import (
    INURLDetailViewCounter,
    StandardInformationKeyword,
    StandardInformationURL,
)
from common.package.naver_search import get_search_data
from common.services import naver_in


base_data_router = Router()


# ────────────────────────────────────────────────────────────────────────────
# 운영 데이터 입력 — 기준정보 업로드
# ────────────────────────────────────────────────────────────────────────────

@base_data_router.post(
    "/keyword",
    auth=None,
)
def upload_keyword_base_data(
    request,
    file: UploadedFile = File(None),
):
    StandardInformationKeyword.objects.all().delete()

    data = pd.read_excel(file)

    for row in data.values.tolist():
        StandardInformationKeyword.objects.get_or_create(
            product=row[0],
            keyword=row[1],
            priority=row[2],
        )

    return {"message": "키워드 파일 업로드 완료."}


@base_data_router.post(
    "/url",
    auth=None,
)
def upload_url_base_data(
    request,
    file: UploadedFile = File(None),
):
    StandardInformationURL.objects.all().delete()

    data = pd.read_excel(file)

    for row in data.values.tolist():
        StandardInformationURL.objects.get_or_create(
            url=row[0],
            product=row[1],
            conversion_keyword=row[2],
            manuscript_form=row[3],
            publication_keyword=row[4],
        )

    return {"message": "URL 파일 업로드 완료."}


@base_data_router.post(
    "/new/url",
    auth=None,
)
def upload_new_url_base_data(
    request,
    file: UploadedFile = File(None),
):
    INURLDetailViewCounter.objects.all().delete()

    data = pd.read_excel(file)

    for row in data.values.tolist():
        INURLDetailViewCounter.objects.get_or_create(
            product=row[0],
            keyword=row[1],
            url=row[2],
            answer_code=row[3],
        )

    return {"message": "NEW URL 파일 업로드 완료."}


# ────────────────────────────────────────────────────────────────────────────
# 디버그 트리거 — 운영 cron 과 동일한 서비스 호출
# ────────────────────────────────────────────────────────────────────────────

@base_data_router.get("/test-result", auth=None)
def trigger_build_daily_excel(request, date: str):
    """``date`` 일자 ``DailyResult`` 로 엑셀 + S3 + 메일 발사 (수신자는 env 로 조절).

    cron 14시 task 와 동일한 산출물. 메일·S3 부수효과 발생.
    """
    parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    return naver_in.build_daily_excel(parsed_date)


@base_data_router.get("/test-collect", auth=None)
def trigger_collect_daily_kin(request, limit: int = 5):
    """``collect_daily_kin`` 동기 실행, 처음 ``limit`` 개 키워드만.

    cron 0시 task 의 부분 실행 — staging 에서 5개 정도로 빠르게 검증할 때 사용.
    실제 ``DailyResult`` row 가 만들어지므로 부수효과 있음.
    """
    return naver_in.collect_daily_kin(limit=limit)


@base_data_router.get("/test-detail-page", auth=None)
def trigger_collect_detail_view(request, limit: int = 5):
    """``collect_detail_view`` 동기 실행, 처음 ``limit`` 개 row 만.

    cron 21시 task 의 부분 실행. 메일 부수효과 발생 (수신자는 env 로 조절).
    """
    return naver_in.collect_detail_view(limit=limit)


@base_data_router.get("/test-href", auth=None)
def test_api_href(request, href: str):
    """단일 지식인 상세 URL 의 작성자/조회수/댓글 파싱 디버그."""
    ip_addresses = naver_in._load_ip_addresses()

    response_matching_data, _ = get_search_data(href, ip_addresses)
    if response_matching_data.status_code != 200:
        return {"status_code": response_matching_data.status_code}

    soup = BeautifulSoup(response_matching_data.text, 'html.parser')
    left_texts = soup.select(
        '#endArea > div.contentArea.contentArea--question._questionArea > div.userInfo.userInfo__bullet > span'
    )
    comment_button = soup.select(
        '#endArea > div.contentArea.contentArea--question._questionArea > div.contentButtonArea._questionBottomMenu > div.contentButtonLeft > button._questionComment'
    )

    try:
        comment_span = comment_button[0].select('span')[-1]
        comment_count = comment_span.text.strip()

        first_text = left_texts[0].text.replace(" ", "")

        if first_text == '비공개':
            first_text = left_texts[1].text.replace(" ", "").replace("조회수", "")
            second_text = left_texts[2].text.replace(" ", "")
        else:
            first_text = left_texts[0].text.replace(" ", "").replace("조회수", "")
            second_text = left_texts[1].text.replace(" ", "")

        return {
            "views": first_text,
            "date": second_text[:-1],
            "comment_count": comment_count,
        }
    except Exception as e:
        return {"error": str(e)}
