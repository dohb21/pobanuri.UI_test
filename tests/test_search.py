import random
import time
import urllib.parse
from playwright.sync_api import Page
from .base import close_popups

# 검색 결과 URL 파라미터 (form 의 hidden field 포함)
SEARCH_RESULT_PATH = "/search/searchResult"
SEARCH_HIDDEN_PARAMS = "cookieFlag=1&reSearchFlag=N"


def _do_search(page: Page, url: str, keyword: str, first_search: bool = True):
    """
    검색 실행.
    1단계: UI 검색 (검색레이어 btn 클릭 → input#searchQuery fill → Enter)
    2단계: URL 직접 이동 (1단계 실패 또는 결과 페이지 미도달 시)
    """
    # 첫 번째 검색이거나 현재 URL이 검색 결과 페이지가 아니면 메인 페이지로 이동
    if first_search or SEARCH_RESULT_PATH not in page.url:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        close_popups(page)
    else:
        # 이미 검색 결과 페이지면 팝업만 닫기
        try:
            close_popups(page)
        except Exception:
            pass

    # 1단계: UI 검색 시도
    try:
        # 검색 레이어 열기 버튼 클릭 (input.dev-header-searchLayer-btn 등)
        for open_sel in [
            "input.dev-header-searchLayer-btn",
            "input.dev-header-lookupLayer-btn",
            ".btn-search",
        ]:
            try:
                el = page.locator(open_sel).first
                if el.is_visible(timeout=1500):
                    el.click(timeout=2000)
                    time.sleep(0.5)
                    break
            except Exception:
                continue

        # 실제 검색 form 의 input 찾기
        inp = None
        for sel in [
            "input#searchQuery",
            "input[name='searchQuery']",
            "form#headerSearch input[type='text']:not([style*='display:none'])",
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    inp = el
                    break
            except Exception:
                continue

        if inp is not None:
            # 부모 컨테이너까지 강제 표시
            inp.evaluate("""el => {
                el.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important;';
                let p = el.parentElement;
                for (let i = 0; i < 6 && p && p !== document.body; i++, p = p.parentElement) {
                    if (getComputedStyle(p).display === 'none') p.style.display = 'block';
                }
            }""")
            try:
                inp.click(timeout=2000)
            except Exception:
                inp.evaluate("el => el.focus()")
            time.sleep(0.3)
            inp.fill(keyword)
            time.sleep(0.3)
            inp.press("Enter")
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            time.sleep(1.5)
    except Exception:
        pass

    # 검색 결과 페이지 미도달 시 URL 직접 이동
    if SEARCH_RESULT_PATH not in page.url:
        base = url.replace("/main", "")
        encoded = urllib.parse.quote(keyword)
        search_url = f"{base}{SEARCH_RESULT_PATH}?{SEARCH_HIDDEN_PARAMS}&searchQuery={encoded}"
        page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)

    # AJAX 결과 로드 대기 (#searchUnitList 가 채워질 때까지)
    try:
        page.wait_for_selector("#searchUnitList li", timeout=8000)
    except Exception:
        pass
    time.sleep(0.5)


def _count_results(page: Page) -> int:
    """
    유효 검색어용 결과 카운트.
    PC: #searchUnitList li  |  Mobile: a[href*='indexGoodsDetail?goodsId=']
    검색 결과 페이지에는 사이드바가 없으므로 링크 카운트 안전.
    """
    try:
        cnt = page.locator("#searchUnitList li").count()
        if cnt > 0:
            return cnt
    except Exception:
        pass
    # Mobile fallback (검색결과 페이지에선 사이드바 없음)
    try:
        cnt = page.locator("a[href*='/goods/indexGoodsDetail?goodsId=']").count()
        if cnt > 0:
            return cnt
    except Exception:
        pass
    return 0


def _has_no_result(page: Page) -> bool:
    """결과없음 메시지 확인"""
    try:
        if "검색 결과가 없" in page.content():
            return True
    except Exception:
        pass
    try:
        if page.locator("text=검색 결과가 없").count() > 0:
            return True
    except Exception:
        pass
    return False


def run(page: Page, url: str, valid_keywords: list) -> str:
    chosen_valid = random.sample(valid_keywords, min(3, len(valid_keywords)))
    errors = []
    ok_list = []

    for idx, kw in enumerate(chosen_valid):
        try:
            _do_search(page, url, kw, first_search=(idx == 0))
            count = _count_results(page)
            assert count > 0, f"'{kw}' 검색 결과 상품 없음"
            ok_list.append(f"'{kw}'({count}개)")
        except Exception as e:
            errors.append(f"'{kw}': {str(e)[:60]}")

    if errors:
        raise AssertionError("; ".join(errors))

    return ", ".join(ok_list)
