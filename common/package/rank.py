# apps/collector/utils/rank_utils.py
from typing import Optional

from bs4 import BeautifulSoup, Tag


def _rank_by_block_inner_selector(soup: BeautifulSoup, inner_selector: str) -> int:
    """
    페이지의 모든 섹션 블록(div.api_subject_bx)을 순서대로 훑으면서,
    각 블록 내부에 inner_selector에 해당하는 요소가 존재하면 해당 블록의
    순번(1부터)을 반환. 없으면 0.
    """
    blocks = soup.select("div.api_subject_bx")
    for idx, block in enumerate(blocks, start=1):
        if block.select_one(inner_selector):
            return idx
    return 0


def _rank_by_section_classes(soup: BeautifulSoup, section_class: str) -> int:
    """
    section_class 예: 'sc sp_nkin _fe_kin_collection'
    1) 해당 클래스를 모두 가진 <section>을 찾고
    2) 그 섹션 내부의 첫 div.api_subject_bx를 잡아
    3) 페이지 내 div.api_subject_bx 전체 순서에서의 순번(1부터)을 반환.
    없으면 0.
    """
    # 1) 타겟 섹션 찾기
    classes = [c for c in section_class.split() if c.strip()]
    selector = "section" + "".join(f".{c}" for c in classes)
    section: Optional[Tag] = soup.select_one(selector)
    if not section:
        return 0

    # 2) 섹션 내부의 첫 블록
    target_block: Optional[Tag] = section.select_one("div.api_subject_bx")
    if not target_block:
        return 0

    # 3) 전체 블록들 중 순번 계산
    blocks = soup.select("div.api_subject_bx")
    for idx, block in enumerate(blocks, start=1):
        if block is target_block:
            return idx
    return 0


def get_section_rank(soup: BeautifulSoup, section_class: str) -> int:
    """
    (리팩토링) 섹션의 순번(1부터)을 반환. 기존 시그니처 유지.
    내부 구현을 '섹션→블록 매핑' 방식으로 바꿔 신뢰도를 높였다.
    예) 'sc sp_nkin _fe_kin_collection' (지식인 섹션)
    """
    return _rank_by_section_classes(soup, section_class)


def get_influencer_rank(soup: BeautifulSoup) -> int:
    """
    인플루언서 섹션 순번(1부터) 반환. 없으면 0.
    get_ad_rank와 동일한 '블록 내부 선택자' 방식 사용.
    """
    return _rank_by_block_inner_selector(soup, "div.fds-ugc-influencer")


def get_ad_rank(soup: BeautifulSoup) -> int:
    """
    광고 섹션(div.fds-news-item-list)이 포함된 블록의 순번(1부터).
    없으면 0.
    (기존 동작을 일반화된 헬퍼로 구현)
    """
    return _rank_by_block_inner_selector(soup, "div.fds-news-item-list")


def get_kin_rank(soup: BeautifulSoup) -> int:
    """
    광고 섹션(div.fds-news-item-list)이 포함된 블록의 순번(1부터).
    없으면 0.
    (기존 동작을 일반화된 헬퍼로 구현)
    """
    return _rank_by_block_inner_selector(soup, "div.fds-kin-item-list")