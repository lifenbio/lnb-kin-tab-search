"""``common.services.naver_in`` 의 공유 헬퍼 회귀 테스트.

리팩토링 시 ``base_data.py`` 와 ``tasks.py`` 양쪽에 중복돼 있던 헬퍼를 한 곳으로
모았다. 이 테스트는 그 헬퍼들이 운영 코드 (cron 으로 도는 ``tasks.py``) 가 의존하던
동작을 그대로 유지하는지 보장한다.

서비스 함수 (``collect_daily_kin``, ``build_daily_excel``, ``collect_detail_view``)
자체의 회귀 검증은 prod 베이스라인 엑셀과의 ``pandas.testing.assert_frame_equal``
비교로 수행 — 이 테스트 범위 밖.
"""

from django.test import TestCase

from common.models import StandardInformationURL
from common.services.naver_in import (
    check_ids_match,
    find_matching_data,
    get_normalized_url,
    parse_query_params,
)


class ParseQueryParamsTests(TestCase):
    def test_extracts_dirid_docid(self):
        url = "https://m.kin.naver.com/qna/detail.naver?d1id=11&dirId=11080104&docId=482945001"
        params = parse_query_params(url)
        self.assertEqual(params["dirId"], "11080104")
        self.assertEqual(params["docId"], "482945001")

    def test_empty_query(self):
        self.assertEqual(parse_query_params("https://example.com/path"), {})

    def test_duplicate_keys_takes_first(self):
        # parse_qs 는 같은 키가 여러 번 나오면 list 로 반환. 우리 헬퍼는 v[0] 만.
        url = "https://example.com/?k=a&k=b"
        self.assertEqual(parse_query_params(url), {"k": "a"})


class CheckIdsMatchTests(TestCase):
    def test_both_match(self):
        a = "https://kin.naver.com/qna/detail.naver?dirId=11&docId=42"
        b = "https://m.kin.naver.com/qna/detail.naver?docId=42&dirId=11"
        self.assertTrue(check_ids_match(a, b))

    def test_only_dirid_matches(self):
        a = "https://kin.naver.com/qna/detail.naver?dirId=11&docId=42"
        b = "https://kin.naver.com/qna/detail.naver?dirId=11&docId=99"
        self.assertFalse(check_ids_match(a, b))

    def test_only_docid_matches(self):
        a = "https://kin.naver.com/qna/detail.naver?dirId=11&docId=42"
        b = "https://kin.naver.com/qna/detail.naver?dirId=22&docId=42"
        self.assertFalse(check_ids_match(a, b))

    def test_missing_params_both_none(self):
        # 파라미터가 양쪽 다 없으면 None == None 으로 매칭됨 — 운영 코드 그대로의 동작
        self.assertTrue(check_ids_match("https://a/", "https://b/"))


class GetNormalizedUrlTests(TestCase):
    def test_strips_scheme_and_query(self):
        url = "https://kin.naver.com/qna/detail.naver?dirId=11&docId=42"
        self.assertEqual(
            get_normalized_url(url),
            "kin.naver.com/qna/detail.naver",
        )


class FindMatchingDataTests(TestCase):
    def setUp(self):
        StandardInformationURL.objects.create(
            url="https://kin.naver.com/qna/detail.naver?dirId=11&docId=42",
            product="prod-A",
            conversion_keyword="kw1",
            manuscript_form="form1",
            publication_keyword="pub1",
        )

    def test_returns_matching_record(self):
        match = find_matching_data("11", "42")
        self.assertIsNotNone(match)
        self.assertEqual(match.product, "prod-A")

    def test_returns_none_when_not_found(self):
        self.assertIsNone(find_matching_data("99", "99"))
