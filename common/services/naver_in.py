"""네이버 지식인 크롤링·집계 도메인 서비스.

원본은 ``common/tasks.py`` 의 ``@shared_task`` 3 종 본체. 매일 cron 으로 도는 운영 코드로
취급되며, 출력(메일·엑셀·DailyResult row) 이 리팩토링 전후로 동일해야 한다.

호출 패턴:
- Celery 태스크 (``common/tasks.py``) 가 wrapper 로 호출 → 정시 자동 실행 경로.
- ``common/api/base_data.py`` 의 ``/test-*`` 엔드포인트가 동일한 함수들을 호출 → 수동
  검증/디버그 트리거. 사소한 차이(메일 수신자, 슬라이스 등) 는 wrapper 단에서 흡수.

추가된 ``_fetch_with_retry``/``_get_view_with_retry`` 는 기존 ``while True`` 무한루프의
안전망. 정상 케이스(매일 cron 산출물 정상 배출) 에서는 한도 안에서 200 응답을 받아
return 되므로 동작은 종전과 동일하며, 한도 초과 시에만 ``CrawlFailure`` 가 발생해
태스크 상위의 ``except Exception`` 으로 흡수된다.
"""

import os
import random
import time
from datetime import datetime, timezone, timedelta
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from common.models import (
    DailyResult,
    INURLDetailViewCounter,
    StandardInformationKeyword,
    StandardInformationURL,
)
from common.package.mail import send
from common.package.naver_search import get_search_data
from common.package.naver_view import get_view_data
from common.package.rank import get_kin_rank
from common.package.storage import s3_client


IP_LIST_PATH = os.environ.get('IP_LIST_PATH', '/app/upload_data/ip_list.txt')


def _split_emails(value):
    """콤마 구분 문자열 → 빈 값 제거한 이메일 리스트."""
    return [e.strip() for e in value.split(',') if e.strip()]


# 메일 수신자 — 운영 기본값은 기존 cron 동작 그대로. staging/디버그 환경에선
# .env.prod 또는 .env.dev 에 ``DAILY_EXCEL_RECIPIENTS`` / ``DETAIL_VIEW_RECIPIENTS``
# 를 본인 메일 등으로 오버라이드해 prod 수신자에게 메일이 가지 않게 격리한다.
DAILY_EXCEL_RECIPIENTS = _split_emails(os.environ.get(
    'DAILY_EXCEL_RECIPIENTS',
    'sh.hwang@lifenbio.com,bangjh@lifenbio.com,jhyjhy@lifenbio.com,chano94@lifenbio.com,min4397@naver.com',
))

DETAIL_VIEW_RECIPIENTS = _split_emails(os.environ.get(
    'DETAIL_VIEW_RECIPIENTS',
    'sh.hwang@lifenbio.com,jhyjhy@lifenbio.com,khbin@lifenbio.com,min4397@naver.com',
))


class CrawlFailure(Exception):
    """네이버 fetch 가 한도 안에서 200 응답을 못 받았을 때 발생."""


def _load_ip_addresses(path=IP_LIST_PATH):
    ip_addresses = []
    with open(path, 'r') as f:
        for line in f:
            ip_addresses.append(line.strip())
    return ip_addresses


def _fetch_with_retry(url, ip_addresses, *, max_attempts=60,
                      ok_sleep=(1, 3), retry_sleep=(5, 10)):
    """``get_search_data`` 를 200 응답이 올 때까지 호출. 한도 초과 시 ``CrawlFailure``.

    정상 케이스: 첫 시도 또는 몇 번째 시도에 200 → 즉시 return. 기존 ``while True`` 와
    동작 동일.

    한도 도달 케이스 (현재 운영에선 발생하지 않음): 60회 후 예외 발생. 기존엔 영원히
    hang 했으나 상위 ``except Exception`` 이 어차피 잡고 task 가 종료되므로 하루치
    산출물 결과는 동일 (둘 다 미생성).
    """
    last_status = None
    for _ in range(max_attempts):
        response, ip = get_search_data(url, ip_addresses)
        time.sleep(random.uniform(*ok_sleep))
        if response.status_code == 200:
            return response, ip
        last_status = response.status_code
        time.sleep(random.uniform(*retry_sleep))
    raise CrawlFailure(f"{url}: {max_attempts}회 재시도 실패 (last_status={last_status})")


def _get_view_with_retry(query, *, max_attempts=20):
    """``get_view_data`` 를 (pc, mobile) 둘 다 not None 일 때까지 호출.

    한도 초과 시 (0, 0) 반환 — 이는 ``get_view_data`` 자체가 비-200 응답에 (0, 0) 을
    반환하던 동작과 동일하므로 다운스트림 처리 결과는 같다.
    """
    for _ in range(max_attempts):
        pc, mobile = get_view_data(query)
        if pc is not None and mobile is not None:
            return pc, mobile
    return 0, 0


def find_matching_data(dirId, docId):
    try:
        matching_data = StandardInformationURL.objects.filter(
            url__contains=f"dirId={dirId}&docId={docId}"
        )
        if matching_data.exists():
            return matching_data.first()
        return None
    except Exception:
        return None


def get_normalized_url(url):
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}"


def parse_query_params(url):
    query_params = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in query_params.items()}


def check_ids_match(row_url, href):
    row_params = parse_query_params(row_url)
    href_params = parse_query_params(href)
    dir_id_match = row_params.get('dirId') == href_params.get('dirId')
    doc_id_match = row_params.get('docId') == href_params.get('docId')
    return dir_id_match and doc_id_match


def collect_daily_kin(*, limit=None):
    """현재 일자 기준 네이버 지식인 키워드 수집 → ``DailyResult`` row 생성.

    ``limit`` 지정 시 처음 N 개 키워드만 처리 (staging/디버그). cron 으로 도는
    ``tasks.py`` 의 wrapper 는 ``limit`` 을 넘기지 않아 운영 동작은 종전과 동일.
    """
    ip_addresses = _load_ip_addresses()

    keyword_qs = StandardInformationKeyword.objects.all().order_by('id')
    if limit is not None:
        keyword_qs = keyword_qs[:limit]

    try:
        for idx, row in enumerate(keyword_qs):
            query = row.keyword
            print(query)

            # 지식인탭
            response, ip_address = _fetch_with_retry(
                f"https://search.naver.com/search.naver?ssc=tab.kin.kqna&where=kin&sm=tab_jum&query={query}",
                ip_addresses,
            )
            # 메인탭
            response_main, _ = _fetch_with_retry(
                f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={query}",
                ip_addresses,
            )

            pc_view, mobile_view = _get_view_with_retry(query)

            soup = BeautifulSoup(response.text, 'html.parser')
            data = soup.select('div.fds-kin-item-list-tab > div')

            main_soup = BeautifulSoup(response_main.text, 'html.parser')
            area_ranking = get_kin_rank(main_soup)

            if data:
                for i, d in enumerate(data[0:3], start=1):
                    result_data = {}
                    print(d)
                    question_links = d.select('a[href*="qna/detail.naver"]')
                    if question_links:
                        href = question_links[0].get('href')
                        try:
                            query = href.split('?')[1]
                            query_dict = dict(q.split('=') for q in query.split('&') if '=' in q)
                            dir_id = query_dict.get('dirId')
                            doc_id = query_dict.get('docId')
                            matching_data = find_matching_data(dir_id, doc_id)
                        except Exception:
                            matching_data = None

                        # 작성자
                        try:
                            author_tag = d.select_one(
                                'div.sds-comps-profile-info-title span.sds-comps-text-type-body1'
                            )
                            author = author_tag.get_text(strip=True) if author_tag else '없음'
                        except:
                            author = '없음'

                        # 뱃지
                        try:
                            badge_tag = d.select_one(
                                'div.sds-comps-profile-info-title span.sds-comps-text-type-badge'
                            )
                            expert_badge = badge_tag.get_text(strip=True) if badge_tag else '없음'
                        except:
                            expert_badge = '없음'

                        # 날짜
                        try:
                            date_tag = d.select_one(
                                'div.sds-comps-profile-info span.sds-comps-profile-info-subtext'
                            )
                            date = date_tag.get_text(strip=True) if date_tag else '없음'
                        except:
                            date = '없음'

                    if matching_data:
                        response_matching_data, _ = _fetch_with_retry(
                            matching_data.url, ip_addresses,
                        )
                        response_matching_data_soup = BeautifulSoup(response_matching_data.text, 'html.parser')
                        left_texts = response_matching_data_soup.select(
                            '#content > div.endContentLeft._endContentLeft > div.contentArea._contentWrap > div.userInfo.userInfo__bullet > span'
                        )
                        try:
                            first_text = left_texts[0].text.replace(" ", "")
                        except:
                            print("first_text = left_texts[0].text.replace(\" \", \"\") ERROR")
                            first_text = "ERROR"

                        try:
                            comment_button = response_matching_data_soup.select_one('span._commentCnt')
                            comment_count = 0
                            if comment_button:
                                comment_count = comment_button.text.strip().rstrip('+')
                            if '정보가없는사용자' in first_text or '비공개' in first_text:
                                first_text = left_texts[1].text.replace(" ", "").replace("조회수", "")
                                second_text = left_texts[2].text.replace(" ", "")
                            else:
                                first_text = left_texts[0].text.replace(" ", "").replace("조회수", "")
                                second_text = left_texts[1].text.replace(" ", "")

                            result_data['transmission_url_date'] = second_text[:-1]
                            result_data['transmission_url_views'] = first_text
                            result_data['transmission_url_comment_cnt'] = comment_count
                        except:
                            result_data['transmission_url_date'] = ''
                            result_data['transmission_url_views'] = ''
                            result_data['transmission_url_comment_cnt'] = ''

                    result_data['keyword_product'] = row.product
                    result_data['keyword'] = row.keyword
                    result_data['priority'] = row.priority

                    result_data['ranking'] = i
                    result_data['name'] = author
                    result_data['type'] = expert_badge
                    result_data['question_date'] = date
                    result_data['pc_views'] = pc_view
                    result_data['mobile_views'] = mobile_view

                    result_data['area_ranking'] = area_ranking

                    if matching_data:
                        if row.keyword != matching_data.publication_keyword:
                            result_data['is_subkeyword'] = True
                        result_data['is_transmission'] = True
                        result_data['url'] = matching_data.url
                        result_data['url_product'] = matching_data.product
                        result_data['conversion_keyword'] = matching_data.conversion_keyword
                        result_data['manuscript_form'] = matching_data.manuscript_form
                        result_data['publication_keyword'] = matching_data.publication_keyword

                    DailyResult.objects.create(**result_data)
            else:
                print(f"누락 키워드{row.keyword}")

            random_time = random.uniform(1, 3)
            time.sleep(random_time)

    except Exception as e:
        print(e)
    return "Complete"


def build_daily_excel(date):
    """``date`` 일자 ``DailyResult`` 를 엑셀로 변환 → S3 업로드 + 메일 송부."""
    data = []
    columns = [
        '수집월', '수집월일', '키워드제품명', '매칭키워드', '검색어', '우선순위', '조회수P', '조회수M',
        '영역순위', '순위', 'ID', '송출유무', '질문일자', '종류', 'URL제품명', '전환키워드',
        '원고형태', '발행키워드', '서브유무', 'URL', '상세 조회수', '댓글수', '증가량'
    ]

    queryset = DailyResult.objects.filter(created_dt__date=date).values(
        'created_dt__month',
        'created_dt',
        'keyword_product',
        'keyword',
        'priority',
        'pc_views',
        'mobile_views',
        'area_ranking',
        'ranking',
        'name',
        'is_transmission',
        'question_date',
        'type',
        'url_product',
        'conversion_keyword',
        'manuscript_form',
        'publication_keyword',
        'is_subkeyword',
        'url',
        'transmission_url_views',
        'transmission_url_comment_cnt'
    )

    for row in queryset:
        created_dt = row['created_dt'].strftime('%Y-%m')
        created_dt_with_day = row['created_dt'].strftime('%Y-%m-%d')

        if '주' in row['question_date']:
            question_date = row['question_date']
            question_date = question_date.replace(" ", "").replace("주", "").replace("전", "")
            question_date = row['created_dt'] - timedelta(weeks=int(question_date))
            question_date = question_date.strftime('%Y-%m-%d')
        elif '일' in row['question_date']:
            question_date = row['question_date']
            question_date = question_date.replace(" ", "").replace("일", "").replace("전", "")
            question_date = row['created_dt'] - timedelta(days=int(question_date))
            question_date = question_date.strftime('%Y-%m-%d')
        else:
            question_date = row['question_date']

        # 이전 데이터 가져오기
        previous_date = date - timedelta(days=1)
        previous_data = None

        try:
            if row['is_transmission'] == False:
                # 예외 처리 2: 송출이 안된건 무조건 0입니다.
                difference = 0
            elif len(row['transmission_url_views']) < 1:
                difference = 0
            elif row['is_transmission'] == True:
                while not previous_data and previous_date >= date - timedelta(days=1):  # 4일치 정도 데이터 탐색 (추후 하루로 변경)
                    print(previous_date)
                    previous_data = DailyResult.objects.filter(
                        created_dt__date=previous_date,
                        url=row['url'],
                        keyword=row['keyword']
                    ).first()
                    print(previous_data)
                    if previous_data:
                        break
                    previous_date -= timedelta(days=1)  # 이전 날짜로 이동합니다.

                if previous_data:
                    previous_transmission_url_views = previous_data.transmission_url_views
                    difference = int(row['transmission_url_views'].replace(',', '')) - int(previous_transmission_url_views.replace(',', ''))
                else:
                    difference = 0
        except ValueError:
            difference = 0

        data.append([
            created_dt, created_dt_with_day,
            row['keyword_product'],
            row['keyword'].replace(' ', ''),
            row['keyword'],
            row['priority'],
            row['pc_views'], row['mobile_views'], row['area_ranking'], row['ranking'], row['name'],
            '1' if row['is_transmission'] else '0',
            question_date, row['type'],
            row['url_product'],
            row['conversion_keyword'],
            row['manuscript_form'],
            row['publication_keyword'],
            '1' if row['is_subkeyword'] else '0',
            row['url'],
            row['transmission_url_views'].replace(',', ''),
            row['transmission_url_comment_cnt'],
            difference
        ])

    df = pd.DataFrame(data, columns=columns)

    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)

    key = str(date) + '.xlsx'
    s3_client.put(
        key=key,
        excel_buffer=excel_buffer.getvalue()
    )

    file_list_test = [("result.xlsx", excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]

    send(
        "[지식인] 자사송출 결과",
        "자사송출 결과",
        to=DAILY_EXCEL_RECIPIENTS,
        cc=[],
        files=file_list_test
    )

    return {"message": s3_client.get_s3_url(key)}


def collect_detail_view(*, limit=None):
    """통합검색 PC 페이지에서 우리꺼 노출 여부 + 답변 상위 데이터를 수집해 메일 송부.

    ``limit`` 지정 시 처음 N 개 row 만 처리 (staging/디버그). cron wrapper 는
    ``limit`` 을 넘기지 않아 운영 동작은 종전과 동일.
    """
    date = datetime.now(timezone.utc).date()

    ret_data = []
    columns = [
        '추출일', '제품', '키워드',
        '통검에 지식인글 존재유무', '통검에 우리꺼 노출유무',
        '질문 누적조회수', '질문일자', '답변총갯수', '답변순위',
        '작업수', '답변순위1위여부', '조회수P', '조회수M'
    ]
    ip_addresses = _load_ip_addresses()

    row_qs = INURLDetailViewCounter.objects.all()
    if limit is not None:
        row_qs = row_qs[:limit]

    for row in row_qs:
        # 통합검색(PC) 페이지 fetch
        response, _ = _fetch_with_retry(
            f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={row.keyword}",
            ip_addresses,
        )

        pc_view, mobile_view = _get_view_with_retry(row.keyword)

        soup = BeautifulSoup(response.text, 'html.parser')

        # 네이버 통합검색(PC) 개편 후 지식인 모듈은 data-meta-ssuid="kin" 속성으로 식별
        kin_blocks = soup.select('div[data-meta-ssuid="kin"]')

        # D 통검에 지식인글 존재유무
        kin_block_exists = 1 if kin_blocks else 0

        # E 통검에 우리꺼 노출유무: 지식인 블록 내부 anchor 중 row.url의 dirId/docId와 매칭되는 것이 있는지
        our_exposed = 0
        if kin_block_exists:
            for blk in kin_blocks:
                for link in blk.select('a[href*="qna/detail.naver"]'):
                    href = link.get('href')
                    if href and check_ids_match(row.url, href):
                        our_exposed = 1
                        break
                if our_exposed:
                    break

        question_views = 0
        question_date = 0
        answer_count = 0
        add_box_ranking = 0
        is_answer_ranked_first = 0

        if our_exposed == 1:
            # 우리꺼가 통검에 노출된 경우에만 상세 페이지 fetch 하여 F~I, K 채움
            try:
                response_matching_data, _ = _fetch_with_retry(row.url, ip_addresses)

                response_matching_data_soup = BeautifulSoup(response_matching_data.text, 'html.parser')
                left_texts = response_matching_data_soup.select(
                    '#content > div.endContentLeft._endContentLeft > div.contentArea._contentWrap > div.userInfo.userInfo__bullet > span'
                )

                answer_count_tag = response_matching_data_soup.find("span", class_="_answerCount")
                answer_count = answer_count_tag.get_text(strip=True) if answer_count_tag else 0

                div_list = response_matching_data_soup.find_all("div", class_="contentBox")
                for box_ranking, box in enumerate(div_list, start=1):
                    for p in box.find_all("p"):
                        if row.answer_code in p.get_text(strip=True):
                            add_box_ranking = box_ranking

                try:
                    question_views = left_texts[1].text.replace(" ", "").replace("조회수", "")
                    question_date = left_texts[2].text.replace(" ", "").replace("작성일", "")
                except Exception:
                    question_views = 0
                    question_date = 0

                is_answer_ranked_first = 1 if add_box_ranking == 1 else 0

                random_time = random.uniform(1, 3)
                time.sleep(random_time)
            except Exception as e:
                print(f"row.url fetch/파싱 오류: {e}")

        ret_data.append([
            str(date), row.product, row.keyword,
            kin_block_exists, our_exposed,
            question_views, question_date, answer_count, add_box_ranking,
            1, is_answer_ranked_first, pc_view, mobile_view
        ])

        random_time = random.uniform(1, 3)
        time.sleep(random_time)

    print(ret_data)

    df = pd.DataFrame(ret_data, columns=columns)

    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)

    file_list_test = [("result.xlsx", excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]

    send(
        "[지식인] 답변 상위",
        "답변 상위",
        to=DETAIL_VIEW_RECIPIENTS,
        cc=[],
        files=file_list_test
    )

    return "Complete"
