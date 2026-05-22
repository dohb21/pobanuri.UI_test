import time
from playwright.sync_api import Page
from .base import close_popups


def run(page: Page, url: str) -> str:
    """메인 하단 '카테고리별 인기 상품 추천' 섹션 노출 확인.
    실제 HTML: div.section.sec_6 > ul#categoryMenu + ul#searchUnitList
    페이지 로드 시 JS가 자동으로 첫 탭 클릭해 #searchUnitList에 상품 로드함."""
    page.goto(url, wait_until="load", timeout=25000)
    close_popups(page)

    # 인기상품 섹션 존재 확인
    section = page.locator("div.section.sec_6")
    assert section.count() > 0, "인기상품 섹션(div.section.sec_6)을 찾을 수 없음"

    # 섹션으로 스크롤
    section.first.scroll_into_view_if_needed()
    time.sleep(1.5)

    # 탭 버튼 존재 확인
    tabs = page.locator("#categoryMenu li")
    assert tabs.count() > 0, "카테고리 탭 목록(#categoryMenu li)이 없음"

    # 상품 로드 대기 (JS가 페이지 로드 시 자동 실행)
    try:
        page.wait_for_selector("#searchUnitList li", timeout=8000)
    except Exception:
        pass

    product_count = page.locator("#searchUnitList li").count()
    assert product_count > 0, f"인기상품 목록(#searchUnitList li)에 상품 없음"

    tab_count = tabs.count()
    return f"인기상품 섹션 확인, 탭 {tab_count}개, 상품 {product_count}개"
