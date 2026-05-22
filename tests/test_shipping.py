import time
from playwright.sync_api import Page
from .base import close_popups, login

# 실제 확인된 배송지 관리 URL
SHIPPING_URL_PATH = "/mypage/service/indexAddressList"

# 배송지 추가 버튼: <button class="btn btn-tx" onclick="fn.popupDlvrAddrEdit('');">배송지 추가</button>
ADD_BTN_SELECTORS = [
    "button[onclick*='popupDlvrAddrEdit']",
    "button:has-text('배송지 추가')",
    "a:has-text('배송지 추가')",
]

# 팝업 내 입력 필드 (팝업이 열린 후 확인)
POPUP_FORM_SELECTORS = [
    "input[name*='receiverName'], input[placeholder*='받는']",
    "input[name*='receiverHpNo'], input[name*='phone'], input[placeholder*='전화'], input[placeholder*='휴대']",
    "input[name*='zipCode'], input[name*='postCode'], input[placeholder*='우편']",
    "input[name*='addr'], input[id*='addr'], input[placeholder*='주소']",
]


def run(page: Page, url: str, username: str, password: str) -> str:
    base = url.replace("/main", "")

    # 로그인 (이미 로그인 상태이면 login() 내부에서 즉시 True 반환)
    # 초기 page.goto(url) 제거 – 이전 테스트 navigation 충돌(ERR_ABORTED) 방지
    ok = login(page, url, username, password)
    assert ok, "로그인 실패"

    # 배송지 목록 페이지 직접 이동
    page.goto(base + SHIPPING_URL_PATH, wait_until="domcontentloaded", timeout=15000)
    close_popups(page)
    assert "login" not in page.url.lower(), "배송지 페이지 접근 불가 (로그인 리다이렉트)"

    # 배송지 추가 버튼 클릭
    add_btn = None
    for sel in ADD_BTN_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                add_btn = el
                break
        except Exception:
            continue

    assert add_btn, "배송지 추가 버튼을 찾을 수 없음"
    add_btn.evaluate("el => el.click()")
    time.sleep(1.5)

    # 팝업 내 폼 필드 입력 가능 여부 확인
    field_ok = 0
    for sel in POPUP_FORM_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.fill("테스트")
                el.fill("")
                field_ok += 1
        except Exception:
            continue

    assert field_ok > 0, "배송지 추가 팝업 폼 필드를 찾을 수 없음"
    return f"배송지 추가 팝업 폼 확인 (입력 가능 필드 {field_ok}개)"
