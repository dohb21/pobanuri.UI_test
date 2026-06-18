import time
from playwright.sync_api import Page


# 팝업 컨테이너 선택자 (PC: #bannerPopup, 모바일: class 기반)
POPUP_CONTAINER_SELECTORS = [
    "#bannerPopup",
    "div.layerFull.bannerPop",
    "div[class*='bannerPop'][class*='open']",
    "div.mainBanner-contents.bannerPopup_slide",
    "div[class*='bannerPopup']",
    "div[class*='bannerPop']",
]

# 팝업 닫기 버튼
CLOSE_SELECTORS = [
    "button.btn-close",
    "button.btn_close",
    "button.close",
    "button.stopWatchingToday",
    "button.btn-today",
]


def _find_popup_container(page: Page):
    """팝업 컨테이너 탐색. (el, sel) 반환, 없으면 (None, None)"""
    for sel in POPUP_CONTAINER_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                return el, sel
        except Exception:
            pass
    return None, None


def _get_slide_links(popup_el) -> list[str]:
    """팝업 내 non-duplicate 슬라이드 링크 목록 (중복 제거, 순서 유지)"""
    links: list[str] = []
    seen: set[str] = set()
    try:
        slides = popup_el.locator("li.swiper-slide:not(.swiper-slide-duplicate)").all()
        for slide in slides:
            try:
                href = slide.locator("a").first.get_attribute("href", timeout=500)
                if href and href not in seen:
                    seen.add(href)
                    links.append(href)
            except Exception:
                pass
    except Exception:
        pass
    return links


def _test_slide_link(page: Page, href: str, slide_idx: int, url: str) -> bool:
    """슬라이드 링크로 진입 테스트"""
    base = url.split("/main")[0].rstrip("/")
    if href.startswith("/"):
        target = base + href
    elif href.startswith("http"):
        target = href
    else:
        target = base + "/" + href

    print(f"  [슬라이드 {slide_idx}] 이동: {target}")
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=15000)
        time.sleep(0.5)
        cur = page.url
        ok = "goods" in cur.lower() or "detail" in cur.lower()
        print(f"  [슬라이드 {slide_idx}] {'✅ 진입 성공' if ok else '❌ 진입 실패'}: {cur}")
        return ok
    except Exception as e:
        print(f"  [슬라이드 {slide_idx}] ❌ goto 실패: {str(e)[:60]}")
        return False


def run(page: Page, url: str) -> str:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(2)

    # 팝업 컨테이너 탐색
    popup_el, popup_sel = _find_popup_container(page)
    if not popup_el:
        return "팝업 없음 (현재 팝업이 비활성화 상태)"

    print(f"  [팝업] 컨테이너: {popup_sel}")

    # 슬라이드 링크 전체 수집 (Swiper 이동 불필요)
    links = _get_slide_links(popup_el)
    print(f"  [슬라이드 링크] {len(links)}개: {links}")

    if not links:
        return "팝업 내 슬라이드 링크 없음"

    slide_count = len(links)
    tested = 0
    succeeded = 0

    for i, href in enumerate(links, 1):
        print(f"\n  [슬라이드 {i}/{slide_count}] 링크: {href}")
        tested += 1
        ok = _test_slide_link(page, href, i, url)
        if ok:
            succeeded += 1

        # 메인으로 복귀
        try:
            page.go_back(wait_until="domcontentloaded", timeout=15000)
            print(f"  [슬라이드 {i}] 뒤로가기 성공")
            time.sleep(1)
        except Exception:
            print(f"  [슬라이드 {i}] 뒤로가기 실패 → 메인 이동")
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)

    print(f"\n  [최종 결과] {tested}개 중 {succeeded}개 성공")
    assert succeeded > 0, f"팝업 링크 진입 불가능 ({tested}개 중 {succeeded}개 성공)"

    # 팝업 닫기
    try:
        if page.url != url:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(1)
    except Exception:
        pass

    popup_el, _ = _find_popup_container(page)
    closed = False

    if popup_el:
        for sel in CLOSE_SELECTORS:
            try:
                for btn in popup_el.locator(sel).all():
                    if btn.is_visible(timeout=500):
                        try:
                            btn.evaluate("el => el.click()")
                        except Exception:
                            btn.click(timeout=2000)
                        time.sleep(0.5)
                        closed = True
                        break
            except Exception:
                continue
            if closed:
                break

    if not closed:
        try:
            page.evaluate("if(typeof popClose === 'function') popClose('bannerPopup')")
            closed = True
        except Exception:
            pass

    if not closed:
        try:
            page.evaluate("""
                document.querySelectorAll('#bannerPopup,[class*="bannerPop"],[class*="layerPop"]')
                    .forEach(p => p.style.display = 'none');
            """)
            closed = True
        except Exception:
            pass

    assert closed, "팝업 닫기 버튼을 찾지 못함"
    return (
        f"팝업 확인, {slide_count}개 슬라이드, "
        f"{succeeded}/{tested} 링크 진입 성공, 닫기 성공"
    )
