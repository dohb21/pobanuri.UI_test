import time
from playwright.sync_api import Page
from .base import close_popups


# 실제 GNB 링크 (PC/Mobile 동일)
GNB_ITEMS = [
    ("기획전", "/event/indexEvent?tab=1"),
    ("타임딜", "/event/indexEvent?tab=3"),
]

CONTENT_SELECTORS = [
    "main", "#content", ".content", "[class*='content']",
    ".wrap", "#wrap", "section", "article", ".inner", ".inner1240",
]


def _page_has_content(page: Page) -> bool:
    for sel in CONTENT_SELECTORS:
        try:
            if page.locator(sel).first.is_visible(timeout=2000):
                return True
        except Exception:
            continue
    return False


def _get_base(url: str) -> str:
    return url.split("/main")[0]


def run(page: Page, url: str) -> str:
    base = _get_base(url)
    errors = []
    ok_list = []

    for name, path in GNB_ITEMS:
        try:
            target_url = base + path
            # 링크 클릭보다 직접 goto가 더 안정적
            page.goto(target_url, wait_until="load", timeout=20000)
            close_popups(page)

            assert _page_has_content(page), f"'{name}' 페이지 본문 없음"
            assert path in page.url or page.url != url, f"'{name}' 페이지 이동 안 됨"
            ok_list.append(name)
        except Exception as e:
            errors.append(f"'{name}': {str(e)[:80]}")

    if errors:
        raise AssertionError("; ".join(errors))

    return f"GNB {', '.join(ok_list)} 정상"
