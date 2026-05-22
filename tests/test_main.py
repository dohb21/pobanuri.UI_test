from playwright.sync_api import Page
from .base import close_popups


def run(page: Page, url: str) -> str:
    """메인 화면 진입: 페이지 로드 + 타이틀 확인."""
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    close_popups(page)

    title = page.title()
    assert title, "페이지 타이틀이 비어 있음"

    body = page.locator("body")
    assert body.is_visible(), "body 요소가 보이지 않음"

    return f"url: {url}"
