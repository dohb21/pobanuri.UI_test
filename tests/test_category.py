import random
from playwright.sync_api import Page
from .base import close_popups


def _open_and_click_category_pc(page: Page, category: str) -> bool:
    """PC: categoryOpen() → 대분류 클릭 → 중분류 첫 항목 클릭"""
    try:
        page.evaluate("categoryOpen()")
        page.wait_for_selector(".category-box.on", timeout=5000)

        cat_link = page.locator("#category_depth1 ul.group").get_by_text(category, exact=True)
        if cat_link.count() == 0:
            cat_link = page.locator(".category-box").get_by_text(category, exact=True)
        # 정확 일치 실패 시 첫 세그먼트로 부분 일치 시도 (예: '스포츠/레저/자동차' → '스포츠')
        if cat_link.count() == 0:
            short = category.split("/")[0]
            cat_link = page.locator(".category-box").filter(has_text=short)
        cat_link.first.click(timeout=5000)

        # 중분류(depth2) 나타날 때까지 대기
        for d2_sel in [
            "#category_depth2 a",
            ".category-depth2 a",
            "[id*='depth2'] a",
            "[class*='depth2'] a",
            ".category-box .right a",
            "li[class*='lvl-02']",
            "li[class*='category-lvl-02']",
        ]:
            try:
                page.wait_for_selector(d2_sel, timeout=3000)
                d2 = page.locator(d2_sel).first
                if d2.is_visible(timeout=1000):
                    d2.click(timeout=3000)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    return True
            except Exception:
                continue

        return True
    except Exception:
        return False


def _open_and_click_category_mobile(page: Page, category: str) -> bool:
    """
    Mobile: 전체메뉴 열기 → 대분류 클릭 → 중분류 첫 항목 클릭
    Playwright get_by_role/filter 사용으로 DOM 인덱스 밀림 문제 해결
    """
    def _tap_or_click(el):
        try:
            el.tap(timeout=2000)
        except Exception:
            el.evaluate("el => el.click()")

    try:
        # 1. 전체 메뉴 열기
        menu_opened = False
        for sel in [
            "[onclick*='fn_totalMenuToggle']",
            "img[onclick*='fn_totalMenuToggle']",
            "button[onclick*='fn_totalMenuToggle']",
            "[class*='btnAllMenu']",
            "[class*='btn-all-menu']",
            "[class*='btn_all']",
            "button[class*='menu']",
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    _tap_or_click(el)
                    menu_opened = True
                    break
            except Exception:
                continue

        if not menu_opened:
            return False

        # 2. 대분류(depth1) 링크를 Playwright 텍스트 매칭으로 직접 탐색
        #    all() 스냅샷 방식은 DOM 변경 시 인덱스가 밀려 오동작 → get_by_role 사용
        cat_link = None
        cat_short = category.split("/")[0]

        # 2-a. 정확 일치: get_by_role("link", name=..., exact=True)
        for attempt in [category, cat_short]:
            try:
                loc = page.get_by_role("link", name=attempt, exact=True)
                loc.first.wait_for(state="visible", timeout=3000)
                cat_link = loc.first
                break
            except Exception:
                continue

        # 2-b. 포함 일치: locator("a").filter(has_text=...)
        if cat_link is None:
            try:
                loc = page.locator("a").filter(has_text=cat_short)
                loc.first.wait_for(state="visible", timeout=2000)
                cat_link = loc.first
            except Exception:
                pass

        if cat_link is None:
            return False

        _tap_or_click(cat_link)

        # 3. 중분류(depth2) 대기 후 클릭
        #    poba/samaint/thek: <li class="dev-category-lvl-02" dispclsfno="...">
        for d2_sel in [
            "li[class*='lvl-02']",
            "li[class*='category-lvl']",
            "[class*='depth2'] li",
            "[class*='depth2'] a",
            "[class*='sub'] a",
            "ul.sub-list a",
            "ul.on a",
            "li.on > ul a",
            "li.active > ul a",
        ]:
            try:
                page.wait_for_selector(d2_sel, timeout=2000)
                d2 = page.locator(d2_sel).first
                if d2.is_visible(timeout=1000):
                    _tap_or_click(d2)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    return True
            except Exception:
                continue

        # depth2 없이 depth1 클릭만으로 페이지 이동한 경우도 성공 처리
        return True
    except Exception:
        return False


def _count_products(page: Page) -> int:
    for sel in [
        "#searchUnitList li",
        "a[href*='/goods/indexGoodsDetail']",
        "li.goods-item",
        ".goods-list li",
    ]:
        try:
            cnt = page.locator(sel).count()
            if cnt > 0:
                return cnt
        except Exception:
            continue
    return 0


def run(page: Page, url: str, category_pool: list, count: int, mobile: bool = False) -> str:
    chosen = random.sample(category_pool, min(count, len(category_pool)))
    errors = []
    ok_list = []

    for cat in chosen:
        try:
            for _attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    break
                except Exception:
                    if _attempt == 1:
                        raise
            close_popups(page)

            if mobile:
                success = _open_and_click_category_mobile(page, cat)
            else:
                success = _open_and_click_category_pc(page, cat)

            assert success, "카테고리 메뉴 접근 실패"

            try:
                page.wait_for_selector(
                    "#searchUnitList li, a[href*='/goods/indexGoodsDetail']",
                    timeout=8000
                )
            except Exception:
                pass

            product_count = _count_products(page)
            if product_count == 0:
                # AJAX 로드 지연 시 추가 대기 후 재확인
                try:
                    page.wait_for_selector(
                        "#searchUnitList li, a[href*='/goods/indexGoodsDetail']",
                        timeout=8000
                    )
                except Exception:
                    pass
                product_count = _count_products(page)
            assert product_count > 0, f"카테고리 '{cat}' 상품 없음"
            ok_list.append(f"'{cat}'({product_count}개)")
        except Exception as e:
            errors.append(f"'{cat}': {str(e)[:80]}")

    if errors:
        raise AssertionError("; ".join(errors))

    return ", ".join(ok_list)
