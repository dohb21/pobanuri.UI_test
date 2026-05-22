import random
import time
from playwright.sync_api import Page
from .base import close_popups


def _open_and_click_category_pc(page: Page, category: str) -> bool:
    """PC: categoryOpen() → 대분류 클릭 → 중분류 첫 항목 클릭"""
    try:
        page.evaluate("categoryOpen()")
        page.wait_for_selector(".category-box.on", timeout=5000)
        time.sleep(0.5)

        # 대분류(depth1) 클릭
        cat_link = page.locator("#category_depth1 ul.group").get_by_text(category, exact=True)
        if cat_link.count() == 0:
            cat_link = page.locator(".category-box").get_by_text(category, exact=True)
        cat_link.first.click(timeout=5000)
        time.sleep(0.8)

        # 중분류(depth2) 첫 항목 클릭 → 상품 목록 페이지로 이동
        for d2_sel in [
            "#category_depth2 a",
            ".category-depth2 a",
            "[id*='depth2'] a",
            "[class*='depth2'] a",
            ".category-box .right a",
        ]:
            try:
                d2 = page.locator(d2_sel).first
                if d2.is_visible(timeout=2000):
                    d2.click(timeout=3000)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    time.sleep(1)
                    return True
            except Exception:
                continue

        return True
    except Exception:
        return False


def _open_and_click_category_mobile(page: Page, category: str) -> bool:
    """
    Mobile: fn_totalMenuToggle() 아이콘 클릭 → 대분류 클릭 → 중분류 첫 항목 클릭
    실제 HTML: <img onclick="javascript:fn_totalMenuToggle();">
               <a href="javascript:void(0)">가구/인테리어</a>
               <a href="javascript:void(0)">DIY자재/용품</a>
    """
    try:
        # 1. 전체 메뉴 열기
        menu_opened = False
        for sel in [
            "[onclick*='fn_totalMenuToggle']",
            "img[onclick*='fn_totalMenuToggle']",
            "button[onclick*='fn_totalMenuToggle']",
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    el.evaluate("el => el.click()")
                    time.sleep(1)
                    menu_opened = True
                    break
            except Exception:
                continue

        if not menu_opened:
            return False

        # 2. 대분류(depth1) 클릭 – href="javascript:void(0)" 링크
        d1_found = False
        for d1 in page.locator("a").all():
            try:
                if d1.is_visible(timeout=300) and d1.inner_text(timeout=200).strip() == category:
                    d1.evaluate("el => el.click()")
                    d1_found = True
                    time.sleep(0.8)
                    break
            except Exception:
                continue

        if not d1_found:
            return False

        # 3. 중분류(depth2) 첫 항목 클릭 – depth1 클릭 후 새로 나타난 링크
        # 여러 선택자 시도
        for d2_sel in [
            "[class*='depth2'] a",
            "[class*='sub'] a",
            "ul.sub-list a",
            "ul.on a",
            "li.on > ul a",
            "li.active > ul a",
        ]:
            try:
                d2 = page.locator(d2_sel).first
                if d2.is_visible(timeout=1500):
                    d2.evaluate("el => el.click()")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    time.sleep(1)
                    return True
            except Exception:
                continue

        # depth2 선택자를 못 찾으면: depth1 클릭이 이미 페이지 이동을 했거나
        # depth1 아래에 바로 상품이 있는 구조. URL이 바뀌었으면 성공으로 처리.
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
            # 모바일은 domcontentloaded – load 대기 타임아웃 방지
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
