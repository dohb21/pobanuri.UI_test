import random
from playwright.sync_api import Page
from .base import close_popups


def _safe_click(el):
    """scroll → click(force) → JS click 순으로 시도"""
    try:
        el.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        el.click(timeout=3000, force=True)
    except Exception:
        el.evaluate("el => el.click()")


def _url_changed(page, start_url: str, timeout_ms: int = 3000) -> bool:
    try:
        page.wait_for_function(
            f"() => location.href !== {repr(start_url)}",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


def _open_and_click_category_pc(page: Page, category: str, d2_idx: int = 0) -> bool:
    """PC: depth1 → depth2[d2_idx] → (depth3) 순차 클릭 후 URL 변경 확인"""
    short = category.split("/")[0]
    start_url = page.url
    try:
        # 1) 카테고리 모달 열기 — 버튼 직접 클릭 우선, JS eval 차선
        opened = False
        for btn_sel in [
            "a[href*='categoryOpen']",
            "a[onclick*='categoryOpen']",
            "button[onclick*='categoryOpen']",
        ]:
            try:
                el = page.locator(btn_sel).first
                if el.count() > 0:
                    el.click(timeout=3000, force=True)
                    print(f"  [카테고리 PC] 버튼 클릭 성공 ({btn_sel})")
                    opened = True
                    break
            except Exception:
                continue

        if not opened:
            try:
                page.evaluate("categoryOpen()")
                print("  [카테고리 PC] categoryOpen() JS 호출 성공")
                opened = True
            except Exception as e:
                print(f"  [카테고리 PC] categoryOpen() 실패: {str(e)[:40]}")
                return False

        # 2) 모달 열림 대기
        MODAL_OPEN_SEL = ", ".join([
            ".category-box.on", ".category-box.active", ".category-box.open",
            "#category_depth1 ul.group",
            "[class*='categoryLayer'][style*='display: block']",
            "[class*='categoryLayer'][style*='display:block']",
            "[id*='cateLayer']", "[id*='allCate']",
        ])
        try:
            page.wait_for_selector(MODAL_OPEN_SEL, timeout=4000)
            print("  [카테고리 PC] 모달 열림 확인")
        except Exception:
            print("  [카테고리 PC] 모달 선택자 불일치, 1초 대기 후 진행")
            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass

        # 3) depth1 링크 탐색
        cat_link = None
        for scope_sel in [
            "#category_depth1 ul.group", ".category-box", "#allCateWrap",
            "#cateLayer", "[class*='cateMenu']", "[class*='allCate']",
            "[class*='categoryList']", "[class*='categoryLayer']",
        ]:
            try:
                el = page.locator(scope_sel).get_by_text(category, exact=True)
                if el.count() == 0:
                    el = page.locator(scope_sel).locator("a").filter(has_text=short)
                if el.count() > 0:
                    cat_link = el
                    print(f"  [카테고리 PC] depth1 발견: scope={scope_sel}")
                    break
            except Exception:
                continue

        if cat_link is None or cat_link.count() == 0:
            el = page.locator("a").filter(has_text=short)
            cnt = el.count()
            print(f"  [카테고리 PC] 전체 a 탐색 결과: {cnt}개")
            if cnt > 0:
                cat_link = el

        if cat_link is None or cat_link.count() == 0:
            print(f"  [카테고리 PC] 링크 없음, 실패")
            return False

        _safe_click(cat_link.first)
        print(f"  [카테고리 PC] '{category}' depth1 클릭")

        # URL 변경 시 depth2/3 없이 바로 이동한 경우
        if _url_changed(page, start_url, 2000):
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            print(f"  [카테고리 PC] depth1 클릭으로 이동 완료")
            return True

        # 4) depth2 클릭
        D2_SELS = [
            "#category_depth2 a", ".category-depth2 a",
            "[id*='depth2'] a", "[class*='depth2'] a",
            ".category-box .right a",
            "li[class*='lvl-02'] a", "li[class*='category-lvl-02'] a",
        ]
        d2_clicked = False
        for d2_sel in D2_SELS:
            try:
                page.wait_for_selector(d2_sel, timeout=3000)
                d2_items = page.locator(d2_sel)
                total = d2_items.count()
                if total == 0:
                    continue
                if total <= d2_idx:
                    print(f"  [카테고리 PC] depth2 항목 {total}개, idx={d2_idx} 초과")
                    return False
                d2 = d2_items.nth(d2_idx)
                _safe_click(d2)
                print(f"  [카테고리 PC] depth2[{d2_idx}] 클릭 ({d2_sel})")
                d2_clicked = True
                break
            except Exception:
                continue

        if _url_changed(page, start_url, 3000):
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            print(f"  [카테고리 PC] depth2 클릭으로 이동 완료")
            return True

        # 5) depth3 클릭 (depth2가 sub-panel만 열었을 경우)
        D3_SELS = [
            "#category_depth3 a", ".category-depth3 a",
            "[id*='depth3'] a", "[class*='depth3'] a",
            "li[class*='lvl-03'] a", "li[class*='category-lvl-03'] a",
        ]
        for d3_sel in D3_SELS:
            try:
                page.wait_for_selector(d3_sel, timeout=2000)
                d3 = page.locator(d3_sel).first
                if d3.count() > 0:
                    _safe_click(d3)
                    print(f"  [카테고리 PC] depth3 클릭 ({d3_sel})")
                    if _url_changed(page, start_url, 5000):
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=8000)
                        except Exception:
                            pass
                        print(f"  [카테고리 PC] depth3 클릭으로 이동 완료")
                        return True
                    break
            except Exception:
                continue

        # depth2/3 클릭은 했지만 URL 미변경 — run()에서 URL 체크로 처리
        print(f"  [카테고리 PC] URL 미변경 (현재: {page.url})")
        return True

    except Exception as e:
        print(f"  [카테고리 PC] 예외 발생: {str(e)[:80]}")
        return False


def _open_and_click_category_mobile(page: Page, category: str, d2_idx: int = 0) -> bool:
    """Mobile: 전체메뉴 → depth1 → depth2[d2_idx] → (depth3) 순차 클릭.
    URL 변경 여부는 run()에서 판단하므로 여기서는 클릭 성공 여부만 반환."""
    cat_short = category.split("/")[0]
    start_url = page.url

    def _tap(el):
        try:
            el.tap(timeout=2000)
        except Exception:
            el.evaluate("el => el.click()")

    try:
        # 1) 전체 메뉴 열기
        menu_opened = False
        for sel in [
            "[onclick*='fn_totalMenuToggle']",
            "img[onclick*='fn_totalMenuToggle']",
            "button[onclick*='fn_totalMenuToggle']",
            "[class*='btnAllMenu']", "[class*='btn-all-menu']",
            "[class*='btn_all']", "button[class*='menu']",
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    _tap(el)
                    menu_opened = True
                    break
            except Exception:
                continue
        if not menu_opened:
            print("  [카테고리 Mobile] 메뉴 버튼 없음")
            return False

        # 2) depth1 링크 탐색
        cat_link = None
        for attempt in [category, cat_short]:
            try:
                loc = page.get_by_role("link", name=attempt, exact=True)
                loc.first.wait_for(state="visible", timeout=3000)
                cat_link = loc.first
                break
            except Exception:
                continue
        if cat_link is None:
            try:
                loc = page.locator("a").filter(has_text=cat_short)
                loc.first.wait_for(state="visible", timeout=2000)
                cat_link = loc.first
            except Exception:
                pass
        if cat_link is None:
            print(f"  [카테고리 Mobile] depth1 '{category}' 링크 없음")
            return False

        _tap(cat_link)
        print(f"  [카테고리 Mobile] '{category}' depth1 클릭")

        # depth1 클릭으로 바로 이동하는 경우
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        if page.url != start_url:
            print(f"  [카테고리 Mobile] depth1 클릭으로 이동 완료")
            return True

        # 3) depth2[d2_idx] 클릭
        D2_SELS = [
            "li[class*='lvl-02']", "li[class*='category-lvl']",
            "[class*='depth2'] li", "[class*='depth2'] a",
            "[class*='sub'] a", "ul.sub-list a",
            "ul.on a", "li.on > ul a", "li.active > ul a",
        ]
        d2_clicked = False
        for d2_sel in D2_SELS:
            try:
                page.wait_for_selector(d2_sel, timeout=2000)
                d2_items = page.locator(d2_sel)
                total = d2_items.count()
                if total == 0:
                    continue
                if total <= d2_idx:
                    print(f"  [카테고리 Mobile] depth2 {total}개, idx={d2_idx} 초과")
                    return False
                _tap(d2_items.nth(d2_idx))
                print(f"  [카테고리 Mobile] depth2[{d2_idx}] 클릭")
                d2_clicked = True
                break
            except Exception:
                continue

        if not d2_clicked:
            # depth2가 없고 depth1 클릭 후 이미 페이지 이동 중일 수 있음
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return True

        # depth2 클릭 후 이동 대기
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        if page.url != start_url:
            print(f"  [카테고리 Mobile] depth2 클릭으로 이동 완료")
            return True

        # 4) depth3 클릭 (depth2가 sub-panel만 열었을 경우)
        D3_SELS = [
            "li[class*='lvl-03'] a", "li[class*='category-lvl-03'] a",
            "[id*='depth3'] a", "[class*='depth3'] a",
        ]
        for d3_sel in D3_SELS:
            try:
                page.wait_for_selector(d3_sel, timeout=2000)
                d3 = page.locator(d3_sel).first
                if d3.count() > 0 and d3.is_visible(timeout=500):
                    _tap(d3)
                    print(f"  [카테고리 Mobile] depth3 클릭 ({d3_sel})")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    return True
            except Exception:
                continue

        # 클릭은 했지만 URL 미변경 — run()에서 URL 체크로 처리
        print(f"  [카테고리 Mobile] URL 미변경 (현재: {page.url})")
        return True
    except Exception as e:
        print(f"  [카테고리 Mobile] 예외 발생: {str(e)[:80]}")
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

    nav_fn = _open_and_click_category_mobile if mobile else _open_and_click_category_pc
    PRODUCT_SEL = "#searchUnitList li, a[href*='/goods/indexGoodsDetail']"

    for cat in chosen:
        product_count = 0
        last_error = f"카테고리 '{cat}' 상품 없음"
        try:
            for d2_idx in range(4):  # depth2 항목을 최대 4개까지 시도
                # 매 시도마다 메인으로 돌아가서 재시작
                for _attempt in range(2):
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=25000)
                        break
                    except Exception:
                        if _attempt == 1:
                            raise
                close_popups(page)

                success = nav_fn(page, cat, d2_idx=d2_idx)
                if not success:
                    last_error = "카테고리 메뉴 접근 실패" if d2_idx == 0 else last_error
                    break

                final_url = page.url
                print(f"  [카테고리] '{cat}' [d2:{d2_idx}] URL: {final_url}")

                if final_url.rstrip("/") == url.rstrip("/"):
                    last_error = "카테고리 페이지 이동 없음 (여전히 메인)"
                    continue  # 다음 d2_idx 시도

                # 상품 로드 대기 후 카운트
                try:
                    page.wait_for_selector(PRODUCT_SEL, timeout=8000)
                except Exception:
                    pass
                product_count = _count_products(page)
                if product_count == 0:
                    try:
                        page.wait_for_selector(PRODUCT_SEL, timeout=5000)
                    except Exception:
                        pass
                    product_count = _count_products(page)

                if product_count > 0:
                    break
                print(f"  [카테고리] '{cat}' depth2[{d2_idx}] 상품 없음, 다음 depth2 시도")

            assert product_count > 0, last_error
            print(f"  [카테고리] ✅ '{cat}' 상품 {product_count}개")
            ok_list.append(f"'{cat}'({product_count}개)")
        except Exception as e:
            errors.append(f"'{cat}': {str(e)[:80]}")

    if errors:
        raise AssertionError("; ".join(errors))

    return ", ".join(ok_list)
