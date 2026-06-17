import random
import time
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
    Mobile: fn_totalMenuToggle() 아이콘 클릭 → 대분류 클릭 → 중분류 첫 항목 클릭
    """
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
                    el.evaluate("el => el.click()")
                    try:
                        page.wait_for_selector(
                            "[class*='totalMenu'], [class*='total-menu'], [class*='allMenu'], "
                            "[class*='all-menu'], [class*='gnbAll'], [class*='sideMenu']",
                            timeout=3000
                        )
                    except Exception:
                        time.sleep(0.5)
                    menu_opened = True
                    break
            except Exception:
                continue

        if not menu_opened:
            return False

        # 메뉴 링크가 렌더링될 때까지 대기
        try:
            page.wait_for_function("() => document.querySelectorAll('a').length > 5", timeout=2000)
        except Exception:
            pass

        # 2. 대분류(depth1) 클릭 — 정확 일치 우선, 없으면 포함 일치
        d1_found = False
        all_links = page.locator("a").all()

        def _normalize(text: str) -> str:
            return " ".join(text.split())  # 탭·줄바꿈·다중공백 정규화

        def _click_el(el):
            """모바일 tap 우선, 실패 시 evaluate click"""
            try:
                el.tap(timeout=2000)
            except Exception:
                el.evaluate("el => el.click()")

        # 정확 일치
        for d1 in all_links:
            try:
                if not d1.is_visible(timeout=300):
                    continue
                text = _normalize(d1.inner_text(timeout=200))
                if text == category:
                    _click_el(d1)
                    d1_found = True
                    break
            except Exception:
                continue

        # 포함 일치 (예: '문구/취미/펫' → '문구/취미')
        if not d1_found:
            cat_short = category.split("/")[0]  # 첫 번째 슬래시 이전
            for d1 in all_links:
                try:
                    if not d1.is_visible(timeout=200):
                        continue
                    text = _normalize(d1.inner_text(timeout=200))
                    if cat_short and cat_short in text and len(text) < 30:
                        _click_el(d1)
                        d1_found = True
                        break
                except Exception:
                    continue

        if not d1_found:
            return False

        # 3. 클릭 후 URL 변경(페이지 이동) 또는 중분류 노출 대기
        try:
            page.wait_for_function(
                "() => location.href.includes('indexCategory') || location.href.includes('/category')",
                timeout=3000,
            )
            # 직접 카테고리 페이지로 이동
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            return True
        except Exception:
            pass

        # 중분류(depth2) 나타날 때까지 대기 후 클릭
        # poba/samaint/thek: <li class="dev-category-lvl-02" dispclsfno="..."> 구조
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
                    _click_el(d2)
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
            wait = "domcontentloaded" if mobile else "load"
            page.goto(url, wait_until=wait, timeout=25000)
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
            assert product_count > 0, f"카테고리 '{cat}' 상품 없음"
            ok_list.append(f"'{cat}'({product_count}개)")
        except Exception as e:
            errors.append(f"'{cat}': {str(e)[:80]}")

    if errors:
        raise AssertionError("; ".join(errors))

    return ", ".join(ok_list)
