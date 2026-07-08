import re
import time
from playwright.sync_api import Page
from .base import close_popups, login

POPULAR_CART_BTN_SELECTORS = [
    "#searchUnitList button.btn_cart",
    "#searchUnitList button[id*='cartAdd']",
    "#searchUnitList button[onclick*='cartAdd']",
    "#searchUnitList [class*='btn_cart']",
    "div.section.sec_6 button.btn_cart",
    "div.section.sec_6 button[onclick*='cartAdd']",
]

DETAIL_CART_BTN_SELECTORS = [
    "button#btnGoodsDtlCart",
    "button.btn-cart[id*='DtlCart']",
    "button.btn-cart",
    "button[id*='DtlCart']",
    "button[id*='btnCart']",
]

CART_ITEM_SELECTORS = [
    "[class*='cartItem']",
    "[class*='cart-item']",
    "[class*='cartPrd']",
    "[class*='goodsNm']",
    ".prd-name",
    "[class*='cart_list'] li",
    ".orderList li",
    ".cartList li",
    "table[class*='cart'] tr:not(:first-child)",
    "input[type='checkbox'][name*='goods']",
    "input[type='checkbox'][name*='prd']",
    "input[type='checkbox'][name*='cart']",
    "input[type='checkbox'][id*='chk']",
    "input[type='number']",
]

CART_PATHS = ["/order/indexCartList", "/cart", "/basket"]

ORDER_BTN_SELECTORS = [
    "button[name='orderBtn']",
    "button.btn.lg.primary[name='orderBtn']",
    "button.btn-basicL[name='orderBtn']",
    "button:has-text('주문하기')",
]

ORDER_PAYMENT_PATH = "/order/indexOrderPayment"

# 주문하기 클릭 후 허용되는 목적지 URL 패턴 (배송지 선택 페이지도 허용)
CHECKOUT_PATHS = [
    "/order/indexOrderPayment",
    "/mypage/order/indexDeliveryList",
    "/order/indexDeliveryList",
    "/order/indexDelivery",
    "/mypage/order/indexDelivery",
]

CART_URL_PATTERNS = ["indexCartList", "/cart", "/basket"]


def _goto_cart(page: Page, base_url: str):
    base = base_url.replace("/main", "").rstrip("/")
    for path in CART_PATHS:
        try:
            page.goto(base + path, wait_until="domcontentloaded", timeout=15000)
            close_popups(page)
            return
        except Exception:
            continue


def _count_cart_items(page: Page, base_url: str = "") -> int:
    if base_url:
        base = base_url.replace("/main", "").rstrip("/")
        try:
            count = page.evaluate("""(base) => {
                return fetch(base + '/common/getCartCnt?temp=' + new Date().toString())
                    .then(r => r.json())
                    .then(d => typeof d.cartCnt !== 'undefined' ? d.cartCnt : -1)
                    .catch(() => -1);
            }""", base)
            if isinstance(count, (int, float)) and count > 0:
                return int(count)
        except Exception:
            pass
    for sel in CART_ITEM_SELECTORS:
        try:
            cnt = page.locator(sel).count()
            if cnt > 0:
                return cnt
        except Exception:
            continue
    return 0


def _empty_cart(page: Page, base_url: str) -> int:
    """장바구니 비우기. 최종 항목 수 반환."""
    _goto_cart(page, base_url)
    for sel in [
        "input[type='checkbox'][id*='all']",
        "input[type='checkbox'][id*='All']",
        "input[type='checkbox'][class*='all']",
        "input[type='checkbox'][name*='all']",
    ]:
        try:
            chk = page.locator(sel).first
            if chk.count() > 0 and chk.is_visible(timeout=800):
                if not chk.is_checked():
                    try:
                        chk.check(timeout=1500)
                    except Exception:
                        chk.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('click', {bubbles:true})); }")
                break
        except Exception:
            continue
    for sel in [
        "button:has-text('선택삭제')",
        "button:has-text('선택 삭제')",
        "a:has-text('선택삭제')",
        "button:has-text('삭제')",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible(timeout=800):
                try:
                    btn.click(timeout=2000)
                except Exception:
                    btn.evaluate("el => el.click()")
                # 삭제 후 페이지 반응 대기
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                break
        except Exception:
            continue
    try:
        page.reload(wait_until="domcontentloaded", timeout=10000)
        close_popups(page)
    except Exception:
        pass
    return _count_cart_items(page, base_url)


def _scroll_to_popular(page: Page):
    """하단 인기상품 섹션 스크롤 및 로드 대기"""
    try:
        sec = page.locator("div.section.sec_6").first
        if sec.count() > 0:
            sec.scroll_into_view_if_needed()
        else:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    try:
        page.wait_for_selector("#searchUnitList li", timeout=8000)
    except Exception:
        pass


def _get_popular_hrefs(page: Page, base: str) -> list:
    hrefs = []
    _GOODS_PATTERN = re.compile(r"""['"](/[^'"]*indexGoodsDetail[^'"]*)['"]""")

    def _extract(text: str) -> str:
        if not text:
            return ""
        if "indexGoodsDetail" in text and "javascript:" not in text:
            return text
        m = _GOODS_PATTERN.search(text)
        return m.group(1) if m else ""

    for li in page.locator("#searchUnitList li").all()[:15]:
        try:
            path = ""
            a = li.locator("a[href*='indexGoodsDetail']").first
            if a.count() > 0:
                path = _extract(a.get_attribute("href") or "")

            if not path:
                a2 = li.locator("a[onclick*='indexGoodsDetail']").first
                if a2.count() > 0:
                    path = _extract(a2.get_attribute("onclick") or "")

            if not path:
                a3 = li.locator("a[href^='javascript:']").first
                if a3.count() > 0:
                    path = _extract(a3.get_attribute("href") or "")

            if path:
                hrefs.append(path if path.startswith("http") else base + path)
        except Exception:
            continue
    return hrefs


def _select_first_option(page: Page, container_sel: str = None) -> bool:
    scope = page.locator(container_sel) if container_sel else page
    selected = False

    wraps = scope.locator(".optSelectWrap").all()
    for wrap in wraps:
        container = wrap.locator("label.radio, div.radio").first
        if container.count() == 0:
            continue
        radio = container.locator("input[type='radio']").first
        if radio.count() == 0:
            continue
        try:
            # JS evaluate 우선 — 이벤트 핸들러까지 정확히 발동
            radio.evaluate(
                "el => { el.checked = true;"
                " el.dispatchEvent(new Event('change', {bubbles:true}));"
                " if (window.OnnuriGoodsOptionUtil)"
                " OnnuriGoodsOptionUtil.goodsDtlOptionClick(el); }"
            )
            selected = True
        except Exception:
            try:
                radio.click(timeout=2000, force=True)
                selected = True
            except Exception:
                try:
                    container.click(timeout=2000)
                    selected = True
                except Exception:
                    continue

    if selected:
        return True

    try:
        opt = scope.locator("select").first
        if opt.is_visible(timeout=1000):
            opt.select_option(index=1)
            return True
    except Exception:
        pass
    try:
        radio = scope.locator("input[type='radio']").first
        if radio.is_visible(timeout=500):
            radio.check()
            return True
    except Exception:
        pass
    return False


def _pc_cart_flow(page: Page) -> tuple:
    cart_btn = None
    for sel in POPULAR_CART_BTN_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                cart_btn = btn
                break
        except Exception:
            continue

    if not cart_btn:
        return "", False

    product_name = ""
    try:
        li_el = page.locator("#searchUnitList li").filter(has=cart_btn).first
        name_el = li_el.locator("[class*='goodsNm'], .goods-name, strong, p").first
        product_name = name_el.inner_text(timeout=1000).strip()[:20]
    except Exception:
        pass

    print(f"  [PC 장바구니] 상품 '{product_name}' 장바구니 버튼 클릭 시도")
    try:
        onclick = cart_btn.get_attribute("onclick")
        print(f"  [PC 장바구니] 버튼 onclick: {onclick[:80] if onclick else 'None'}")
    except Exception:
        pass

    try:
        cart_btn.click(timeout=3000)
        print(f"  [PC 장바구니] ✅ click() 성공")
    except Exception as e:
        print(f"  [PC 장바구니] ❌ click() 실패 ({str(e)[:40]}), evaluate로 재시도")
        try:
            cart_btn.evaluate("el => el.click()")
            print(f"  [PC 장바구니] ✅ evaluate click() 성공")
        except Exception as e2:
            print(f"  [PC 장바구니] ❌ evaluate click() 실패 ({str(e2)[:40]})")

    # 상세 장바구니 버튼(팝업) 나타날 때까지 대기
    detail_btn = None
    detail_sel_str = ", ".join(DETAIL_CART_BTN_SELECTORS)
    try:
        page.wait_for_selector(detail_sel_str, timeout=5000)
    except Exception:
        pass

    for sel in DETAIL_CART_BTN_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                detail_btn = btn
                break
        except Exception:
            continue

    if detail_btn:
        print(f"  [PC 장바구니] 상세 장바구니 버튼 발견, 옵션 선택 시도")
        try:
            page.wait_for_selector(".optSelectWrap", timeout=3000)
        except Exception:
            pass
        ok_opt = _select_first_option(page)
        wrap_cnt = page.locator(".optSelectWrap").count()
        print(f"  [PC 장바구니] 옵션 그룹 {wrap_cnt}개, 선택 {'성공' if ok_opt else '실패/없음'}")
        print(f"  [PC 장바구니] 상세 장바구니 버튼 클릭 시도")
        try:
            onclick = detail_btn.get_attribute("onclick")
            print(f"  [PC 장바구니] 버튼 onclick: {onclick[:80] if onclick else 'None'}")
        except Exception:
            pass
        try:
            detail_btn.click(timeout=3000)
            print(f"  [PC 장바구니] ✅ click() 성공")
        except Exception as e:
            print(f"  [PC 장바구니] ❌ click() 실패 ({str(e)[:40]}), evaluate로 재시도")
            try:
                detail_btn.evaluate("el => el.click()")
                print(f"  [PC 장바구니] ✅ evaluate click() 성공")
            except Exception as e2:
                print(f"  [PC 장바구니] ❌ evaluate click() 실패 ({str(e2)[:40]})")

        # 장바구니 추가 완료 신호(dialog 또는 페이지 변화) 대기
        try:
            page.wait_for_function(
                "() => !document.querySelector('button#btnGoodsDtlCart') || "
                "!document.querySelector('button#btnGoodsDtlCart').offsetParent",
                timeout=3000
            )
        except Exception:
            pass
    else:
        print(f"  [PC 장바구니] ⚠️ 상세 장바구니 버튼을 찾을 수 없음")

    return product_name, True


def _mobile_cart_flow(page: Page, base: str) -> tuple:
    hrefs = _get_popular_hrefs(page, base)
    print(f"  [Mobile 장바구니] 인기상품 링크 {len(hrefs)}개 발견")
    assert len(hrefs) >= 1, (
        f"인기상품 링크를 찾을 수 없음 (발견 {len(hrefs)}개)"
    )

    product_name = ""
    print(f"  [Mobile 장바구니] 인기상품 {len(hrefs)}개 순회")
    for href in hrefs[:6]:
        try:
            page.goto(href, wait_until="domcontentloaded", timeout=15000)
            close_popups(page)

            buy_btn = page.locator("button#btnGoodsBuyLayerOpen").first
            if not buy_btn.is_visible(timeout=3000):
                continue

            try:
                title_el = page.locator("h1, h2, [class*='goodsNm'], .goods-name").first
                product_name = title_el.inner_text(timeout=2000).strip()[:20]
            except Exception:
                pass

            print(f"  [Mobile 장바구니] 상품 '{product_name}' 구매하기 버튼 클릭 시도")
            try:
                buy_btn.click(timeout=3000)
            except Exception as e:
                print(f"  [Mobile 장바구니] click() 실패 ({str(e)[:40]}), evaluate로 재시도")
                buy_btn.evaluate("el => el.click()")

            # 옵션 레이어 나타날 때까지 대기
            try:
                page.wait_for_selector("#layerPop-goodsOptionSelect", timeout=3000)
            except Exception:
                pass

            try:
                layer = page.locator("#layerPop-goodsOptionSelect").first
                if layer.is_visible(timeout=1000):
                    wrap_cnt = page.locator(
                        "#layerPop-goodsOptionSelect .optSelectWrap"
                    ).count()
                    print(f"  [Mobile 장바구니] 옵션 레이어 발견, 옵션 그룹 {wrap_cnt}개")
                    ok_opt = _select_first_option(page, "#layerPop-goodsOptionSelect")
                    print(f"  [Mobile 장바구니] 옵션 선택 {'성공' if ok_opt else '실패/없음'}")
            except Exception:
                pass

            for sel in DETAIL_CART_BTN_SELECTORS:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        print(f"  [Mobile 장바구니] 장바구니 버튼 발견 ({sel}), 클릭 시도")
                        try:
                            btn.click(timeout=3000)
                        except Exception as e:
                            print(f"  [Mobile 장바구니] click() 실패 ({str(e)[:40]}), evaluate로 재시도")
                            btn.evaluate("el => el.click()")
                        # 버튼이 사라지거나 dialog가 뜰 때까지 대기
                        try:
                            page.wait_for_function(
                                f"() => !document.querySelector('{sel}') || "
                                f"!document.querySelector('{sel}').offsetParent",
                                timeout=3000
                            )
                        except Exception:
                            pass
                        print(f"  [Mobile 장바구니] ✅ 장바구니 추가 완료")
                        return product_name, True
                except Exception:
                    continue

        except Exception:
            continue

    return product_name, False


def _select_all_cart_items(page: Page):
    """
    장바구니 체크박스를 모두 체크하고, cartOrder 내부 상태를 동기화한다.
    - 이미 체크된 박스도 change 이벤트를 발생시켜 cartOrder.selectedItems를 채운다.
    - click 이벤트는 체크박스를 토글(반전)시키므로 절대 사용하지 않는다.
    """
    for sel in [
        "input[type='checkbox'][id^='up_comp_no_checkbox']",
        "input[type='checkbox'][id*='all']",
        "input[type='checkbox'][id*='All']",
        "input[type='checkbox'][class*='all']",
        "input[type='checkbox'][name*='all']",
    ]:
        try:
            boxes = page.locator(sel).all()
            if not boxes:
                continue
            found_any = False
            for chk in boxes:
                try:
                    if not chk.is_visible(timeout=500):
                        continue
                    found_any = True
                    if not chk.is_checked():
                        try:
                            chk.check(timeout=1500)
                        except Exception:
                            chk.evaluate(
                                "el => { el.checked = true;"
                                " if(window.jQuery) jQuery(el).trigger('change');"
                                " else el.dispatchEvent(new Event('change', {bubbles:true})); }"
                            )
                    else:
                        # 이미 체크됨 — cartOrder 동기화를 위해 change 이벤트만 발생
                        chk.evaluate(
                            "el => { if(window.jQuery) jQuery(el).trigger('change');"
                            " else el.dispatchEvent(new Event('change', {bubbles:true})); }"
                        )
                except Exception:
                    continue
            if found_any:
                print(f"  [주문하기] 전체선택 체크 완료 ({sel}, {len(boxes)}개)")
                return
        except Exception:
            continue
    # 폴백: 모든 체크박스에 change 이벤트 발생 (click 이벤트 없음)
    try:
        cnt = page.evaluate("""() => {
            const boxes = document.querySelectorAll('input[type="checkbox"]');
            boxes.forEach(cb => {
                if (!cb.checked) { cb.checked = true; }
                if (window.jQuery) jQuery(cb).trigger('change');
                else cb.dispatchEvent(new Event('change', {bubbles: true}));
            });
            return boxes.length;
        }""")
        if cnt:
            print(f"  [주문하기] 전체선택 JS 폴백으로 체크박스 {cnt}개 처리")
    except Exception:
        pass


def _is_on_cart_page(page: Page) -> bool:
    return any(p in page.url for p in CART_URL_PATTERNS)


def _wait_for_cart_leave(page: Page, timeout_ms: int = 6000) -> bool:
    """장바구니 URL에서 벗어날 때까지 대기. 이동 성공 시 True."""
    try:
        page.wait_for_function(
            "() => " + " && ".join(
                [f"!location.href.includes('{p}')" for p in CART_URL_PATTERNS]
            ),
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


def _click_order_btn(page: Page) -> bool:
    _select_all_cart_items(page)

    for sel in ORDER_BTN_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.count() == 0:
                continue
            if not btn.is_visible(timeout=2000):
                continue
            print(f"  [주문하기] 버튼 발견 ({sel}), 클릭 시도")

            # 1) tap() — 모바일 컨텍스트에서는 touch 이벤트가 필요
            try:
                btn.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            try:
                btn.tap(timeout=5000)
                print(f"  [주문하기] ✅ tap() 성공, 이동 대기...")
            except Exception as e:
                print(f"  [주문하기] tap() 실패 ({str(e)[:40]}), click 시도")
                try:
                    btn.click(timeout=5000, force=True)
                    print(f"  [주문하기] ✅ click() 성공, 이동 대기...")
                except Exception as e2:
                    print(f"  [주문하기] ❌ click() 실패 ({str(e2)[:40]})")

            if _wait_for_cart_leave(page, 5000):
                return True
            print(f"  [주문하기] 클릭 후 페이지 미변경, cartOrder.buy() 직접 호출")

            # 2) cartOrder 상태 진단 + jQuery 이벤트 갱신 후 cartOrder.buy() 직접 호출
            try:
                debug = page.evaluate("""() => {
                    const checked = document.querySelectorAll('input[type="checkbox"]:checked');
                    const all = document.querySelectorAll('input[type="checkbox"]');
                    const ids = Array.from(checked).slice(0, 5).map(c => c.id || c.name || '?');
                    const classes = Array.from(checked).slice(0, 5).map(c => c.className || '?');
                    const buyFn = (window.cartOrder && cartOrder.buy)
                        ? cartOrder.buy.toString().substring(0, 300) : 'N/A';
                    return {checkedCount: checked.length, totalCount: all.length, ids: ids,
                            classes: classes,
                            hasCartOrder: !!window.cartOrder,
                            hasjQuery: !!window.jQuery,
                            buyFn: buyFn};
                }""")
                print(f"  [주문하기] 진단: checkedCount={debug.get('checkedCount')}, ids={debug.get('ids')}, classes={debug.get('classes')}")
                print(f"  [주문하기] cartOrder.buy 소스: {debug.get('buyFn', 'N/A')[:300]}")
            except Exception:
                pass
            try:
                page.evaluate("""() => {
                    const boxes = document.querySelectorAll('input[type="checkbox"]');
                    boxes.forEach(cb => {
                        if (!cb.checked) { cb.checked = true; }
                        // trigger('change')만 사용 — trigger('click')은 체크박스를 토글(반전)시킴
                        if (window.jQuery) { jQuery(cb).trigger('change'); }
                        else { cb.dispatchEvent(new Event('change', {bubbles:true})); }
                    });
                }""")
                page.evaluate("cartOrder.buy()")
                print(f"  [주문하기] ✅ cartOrder.buy() 호출 성공, 이동 대기...")
            except Exception as e2:
                print(f"  [주문하기] ❌ cartOrder.buy() 실패 ({str(e2)[:40]})")

            if _wait_for_cart_leave(page, 5000):
                return True
            print(f"  [주문하기] cartOrder.buy() 후에도 미변경, evaluate click 시도")

            # 3) 최후 수단
            try:
                btn.evaluate("el => el.click()")
                print(f"  [주문하기] ✅ evaluate click() 성공")
            except Exception:
                pass

            if _wait_for_cart_leave(page, 3000):
                return True

            print(f"  [주문하기] ❌ 모든 방법 실패 (URL: {page.url})")
            return False
        except Exception:
            continue
    return False


def run(page: Page, url: str, username: str, password: str, mobile: bool = False) -> str:
    base = url.replace("/main", "").rstrip("/")
    is_mobile = mobile

    def _safe_accept(d):
        try:
            print(f"  [Dialog] {d.type}: {d.message[:50]}")
            d.accept()
            print(f"  [Dialog] ✅ Accepted")
        except Exception as e:
            print(f"  [Dialog] ⚠️ Error: {str(e)[:40]}")

    page.on("dialog", _safe_accept)

    try:
        ok = login(page, url, username, password)
        assert ok, "로그인 실패"

        print(f"  [장바구니 사전 정리] 장바구니 비우기 시도")
        initial_count = _empty_cart(page, url)
        print(f"  [장바구니 사전 정리] 정리 후 항목 수: {initial_count}")

        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        close_popups(page)
        _scroll_to_popular(page)

        if not is_mobile:
            product_name, success = _pc_cart_flow(page)
            assert success, "인기상품 섹션에서 장바구니 담기 버튼을 찾을 수 없음"
        else:
            product_name, success = _mobile_cart_flow(page, base)
            assert success, "모바일 장바구니 담기 실패 (구매하기→장바구니 흐름 오류)"

        close_popups(page)

        print(f"  [장바구니 확인] 장바구니 페이지로 이동 시도")
        _goto_cart(page, url)
        print(f"  [장바구니 확인] 현재 URL: {page.url}")

        # 장바구니 아이템 로드 대기
        try:
            page.wait_for_selector(", ".join(CART_ITEM_SELECTORS[:4]), timeout=5000)
        except Exception:
            pass

        item_count = _count_cart_items(page, url)
        if item_count == 0:
            try:
                page.wait_for_selector(", ".join(CART_ITEM_SELECTORS[:4]), timeout=5000)
            except Exception:
                pass
            item_count = _count_cart_items(page, url)
        print(f"  [장바구니 확인] 사전 {initial_count}개 → 사후 {item_count}개")

        assert item_count > initial_count, (
            f"장바구니에 상품이 추가되지 않음 (사전 {initial_count}개 → 사후 {item_count}개)"
        )

        close_popups(page)
        print(f"  [주문하기] 주문하기 버튼 클릭 시도")
        order_clicked = _click_order_btn(page)
        assert order_clicked, "주문하기 버튼 클릭 후 페이지 이동 없음"

        current_url = page.url
        print(f"  [주문하기] 현재 URL: {current_url}")
        ok_checkout = any(p in current_url for p in CHECKOUT_PATHS)
        assert ok_checkout, (
            f"결제/배송지 페이지 이동 실패 (현재: {current_url})"
        )
        reached = next(p for p in CHECKOUT_PATHS if p in current_url)
        print(f"  [주문하기] ✅ {reached} 이동 성공")

        try:
            _empty_cart(page, url)
        except Exception:
            pass

        return (
            f"'{product_name}' 장바구니 담기 성공 "
            f"(사전 {initial_count} → 사후 {item_count}), "
            f"주문하기 → {ORDER_PAYMENT_PATH} 이동 성공"
        )

    finally:
        try:
            page.remove_listener("dialog", _safe_accept)
        except Exception:
            pass
