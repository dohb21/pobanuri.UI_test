import re
import time
from playwright.sync_api import Page
from .base import close_popups, login


# 클릭 후 모달/오버레이 감지용 선택자
MODAL_SELECTORS = [
    "[class*='layerCategory']", "[class*='layer-category']",
    "[class*='categoryLayer']", "[class*='category-layer']",
    "[class*='categoryWrap']", "[class*='layerWrap']",
    "[class*='exhibition']", "[class*='Exhibition']",
    "[class*='installment']", "[class*='Installment']",
    "div[class*='layer'][style*='display: block']",
    "div[class*='layer'][style*='display:block']",
    "div[class*='popup'][style*='display: block']",
    "div[class*='popup'][style*='display:block']",
    "div[class*='modal']:not([style*='display: none'])",
    "div[class*='dimmed']:not([style*='display: none'])",
]


def _get_pc_gnb_items(page: Page) -> list[dict]:
    items = []
    lis = page.locator("li._gnbFocus").all()
    for idx, li in enumerate(lis):
        try:
            a = li.locator("a").first
            text = (a.text_content(timeout=500) or "").strip()
            href = a.get_attribute("href") or ""
            onclick = a.get_attribute("onclick") or ""
            if text:
                items.append({"text": text, "href": href, "onclick": onclick, "idx": idx})
        except Exception:
            pass
    return items


def _get_mobile_gnb_items(page: Page) -> list[dict]:
    items = []
    try:
        gnb_ul = page.locator("ul.swiper-wrapper:has(li.swiper-slide > a[href='/main'])").first
        slides = gnb_ul.locator("li.swiper-slide").all()
        for idx, slide in enumerate(slides):
            try:
                a = slide.locator("a").first
                text = (a.text_content(timeout=500) or "").strip()
                href = a.get_attribute("href") or ""
                onclick = a.get_attribute("onclick") or ""
                if text:
                    items.append({"text": text, "href": href, "onclick": onclick, "idx": idx})
            except Exception:
                pass
    except Exception:
        pass
    return items


def _get_item_el(page: Page, item: dict, is_mobile: bool):
    """항목 요소를 페이지에서 새로 탐색해 반환 (stale 방지)"""
    if is_mobile:
        gnb_ul = page.locator("ul.swiper-wrapper:has(li.swiper-slide > a[href='/main'])").first
        return gnb_ul.locator("li.swiper-slide").nth(item["idx"]).locator("a").first
    else:
        return page.locator("li._gnbFocus").nth(item["idx"]).locator("a").first


def _extract_exhibition_id(href: str) -> str | None:
    """javascript:openGnbExhibitionDetail(13342) → '13342'"""
    m = re.search(r'openGnbExhibitionDetail\((\d+)\)', href or "")
    return m.group(1) if m else None


def _is_installment(item: dict) -> bool:
    return (
        "popupInstallment" in (item.get("href") or "")
        or "popupInstallment" in (item.get("onclick") or "")
    )


def _close_any_modal(page: Page):
    """열린 모달/레이어를 ESC 또는 닫기 버튼으로 닫기"""
    try:
        page.keyboard.press("Escape")
        time.sleep(0.3)
    except Exception:
        pass
    close_popups(page)


def _modal_is_open(page: Page) -> bool:
    for sel in MODAL_SELECTORS:
        try:
            if page.locator(sel).first.is_visible(timeout=400):
                return True
        except Exception:
            pass
    # JS 폴백: z-index가 높은 visible 오버레이 요소 탐지
    try:
        return bool(page.evaluate("""() => {
            return Array.from(document.querySelectorAll('div,section,aside')).some(el => {
                const s = window.getComputedStyle(el);
                if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                const z = parseInt(s.zIndex, 10);
                if (!z || z < 100) return false;
                if (el.offsetWidth < 200 || el.offsetHeight < 100) return false;
                const cls = ((el.className && el.className.toString()) || '') + ' ' + (el.id || '');
                return /layer|popup|modal|overlay|dimm|exhibition|installment|category/i.test(cls);
            });
        }"""))
    except Exception:
        return False


def _do_login(page: Page, url: str, username: str, password: str) -> bool:
    """로그인 후 target으로 재이동. 성공 시 True."""
    return login(page, url, username, password)


def _test_regular_link(
    page: Page, item: dict, base: str, url: str, username: str, password: str
) -> tuple[bool, str]:
    """일반 href 링크: 이동 → 로그인 필요 시 로그인 → URL 검증"""
    href = item["href"]
    target = href if href.startswith("http") else base + href
    path_key = href.split("?")[0].rstrip("/").split("/")[-1]

    try:
        page.goto(target, wait_until="domcontentloaded", timeout=15000)
        close_popups(page)
        time.sleep(0.5)

        if "login" in page.url.lower():
            if not username:
                return False, "로그인 필요 (계정 없음)"
            if not _do_login(page, url, username, password):
                return False, "로그인 실패"
            time.sleep(0.5)
            # 로그인 후 대상 페이지로 재이동
            page.goto(target, wait_until="domcontentloaded", timeout=15000)
            close_popups(page)
            time.sleep(0.5)

        cur = page.url
        if href == "/main" or not path_key or path_key in cur:
            return True, f"→ {cur}"
        return False, f"URL 불일치: {cur}"
    except Exception as e:
        return False, str(e)[:80]


def _test_exhibition_link(
    page: Page, item: dict, base: str, url: str, username: str, password: str
) -> tuple[bool, str]:
    """javascript:openGnbExhibitionDetail(id) → /event/indexExhibitionDetail?exhbtNo=id"""
    exhbt_id = _extract_exhibition_id(item["href"])
    if not exhbt_id:
        return False, "기획전 ID 추출 실패"

    target = base + f"/event/indexExhibitionDetail?exhbtNo={exhbt_id}"
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=15000)
        close_popups(page)
        time.sleep(0.5)

        if "login" in page.url.lower():
            if not username:
                return False, "로그인 필요 (계정 없음)"
            if not _do_login(page, url, username, password):
                return False, "로그인 실패"
            time.sleep(0.5)
            page.goto(target, wait_until="domcontentloaded", timeout=15000)
            close_popups(page)
            time.sleep(0.5)

        cur = page.url
        ok = "indexExhibitionDetail" in cur
        return ok, f"→ {cur}"
    except Exception as e:
        return False, str(e)[:80]


def _test_js_link(page: Page, item: dict, is_mobile: bool, start_url: str) -> tuple[bool, str]:
    """JS 링크 클릭 → URL 변경 또는 모달 열림 확인"""
    try:
        el = _get_item_el(page, item, is_mobile)
        try:
            el.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass
        el.click(timeout=5000, force=is_mobile)
        time.sleep(1.5)

        cur = page.url
        if cur != start_url:
            note = "→ 로그인 이동" if "login" in cur.lower() else f"→ {cur}"
            return True, note

        if _modal_is_open(page):
            return True, "모달/오버레이 열림"

        return False, "URL 미변경, 모달 없음"
    except Exception as e:
        return False, str(e)[:80]


def run(page: Page, url: str, username: str = "", password: str = "") -> str:
    base = url.split("/main")[0]
    is_mobile = "mdream" in url or "/m." in url

    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    close_popups(page)
    time.sleep(1)

    items = _get_mobile_gnb_items(page) if is_mobile else _get_pc_gnb_items(page)

    print(f"\n  [GNB] {'모바일' if is_mobile else 'PC'} 메뉴 {len(items)}개 탐지")
    for i, item in enumerate(items):
        print(f"    [{i+1}] '{item['text']}' | href={item['href']} | onclick={item['onclick']}")

    if not items:
        raise AssertionError("GNB 메뉴 항목을 찾을 수 없음")

    results = []
    for i, item in enumerate(items):
        # 각 테스트 전 메인 복귀 및 모달 닫기
        try:
            _close_any_modal(page)
            if page.url != url:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                close_popups(page)
                time.sleep(0.5)
        except Exception:
            pass

        href = item["href"]
        exhbt_id = _extract_exhibition_id(href)
        is_js = not href or href.startswith("javascript:") or href == "#"

        if exhbt_id:
            # javascript:openGnbExhibitionDetail(id) → 직접 URL 구성 후 진입
            ok, note = _test_exhibition_link(page, item, base, url, username, password)
            _close_any_modal(page)
        elif _is_installment(item):
            # popupInstallment(): 클릭 → 모달 감지
            ok, note = _test_js_link(page, item, is_mobile, page.url)
            _close_any_modal(page)
        elif is_js:
            # 기타 JS 링크 (categoryOpen 등): 클릭 → 모달 감지
            ok, note = _test_js_link(page, item, is_mobile, page.url)
            _close_any_modal(page)
        else:
            # 일반 href: 이동 → 로그인 필요 시 로그인 → URL 검증
            ok, note = _test_regular_link(page, item, base, url, username, password)

        status = "✅" if ok else "❌"
        print(f"  [{i+1}/{len(items)}] {status} '{item['text']}': {note}")
        results.append((item["text"], ok, note))

    failed = [(name, note) for name, ok, note in results if not ok]
    ok_count = len(results) - len(failed)
    summary = f"GNB {len(results)}개 중 {ok_count}개 성공"

    if failed:
        detail = ", ".join(f"'{n}': {m}" for n, m in failed)
        raise AssertionError(f"{summary} | 실패: {detail}")

    return summary
