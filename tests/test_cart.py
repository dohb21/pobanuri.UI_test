import re
import time
from playwright.sync_api import Page
from .base import close_popups, login

# PC: 인기상품 섹션의 "장바구니 담기" 버튼 (품절 상품에는 없음)
POPULAR_CART_BTN_SELECTORS = [
    "#searchUnitList button.btn_cart",
    "#searchUnitList button[id*='cartAdd']",
    "#searchUnitList button[onclick*='cartAdd']",
    "#searchUnitList [class*='btn_cart']",
    "div.section.sec_6 button.btn_cart",
    "div.section.sec_6 button[onclick*='cartAdd']",
]

# 최종 "장바구니" 버튼 (PC 팝업 / Mobile 레이어 공통)
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


def _goto_cart(page: Page, base_url: str):
    base = base_url.replace("/main", "")
    for path in CART_PATHS:
        try:
            page.goto(base + path, wait_until="load", timeout=15000)
            close_popups(page)
            return
        except Exception:
            continue


def _count_cart_items(page: Page, base_url: str = "") -> int:
    if base_url:
        base = base_url.replace("/main", "")
        try:
            count = page.evaluate("""(base) => {
                return fetch(base + '/common/getCartCnt?temp=' + new Date().toString())
                    .then(r => r.json())
                    .then(d => typeof d.cartCnt !== 'undefined' ? d.cartCnt : -1)
                    .catch(() => -1);
            }""", base)
            if isinstance(count, (int, float)) and count >= 0:
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
    time.sleep(0.5)
    # 전체선택 체크
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
                time.sleep(0.3)
                break
        except Exception:
            continue
    # 선택삭제 클릭
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
                time.sleep(1.5)
                break
        except Exception:
            continue
    # 페이지 새로고침해서 정확한 잔여 카운트 측정
    try:
        page.reload(wait_until="load", timeout=10000)
        close_popups(page)
        time.sleep(0.5)
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
    time.sleep(1.5)
    try:
        page.wait_for_selector("#searchUnitList li", timeout=8000)
    except Exception:
        pass


def _get_popular_hrefs(page: Page, base: str) -> list:
    """인기상품 섹션에서 상품 URL 목록 반환.
    href / onclick / data-* 등에서 indexGoodsDetail URL 추출.
    """
    hrefs = []
    _GOODS_PATTERN = re.compile(r"""['"](/[^'"]*indexGoodsDetail[^'"]*)['"]""")

    def _extract(text: str) -> str:
        if not text:
            return ""
        if "indexGoodsDetail" in text and "javascript:" not in text:
            return text  # 일반 URL
        m = _GOODS_PATTERN.search(text)
        return m.group(1) if m else ""

    for li in page.locator("#searchUnitList li").all()[:15]:
        try:
            path = ""
            # 1) href 에 indexGoodsDetail 포함
            a = li.locator("a[href*='indexGoodsDetail']").first
            if a.count() > 0:
                path = _extract(a.get_attribute("href") or "")

            # 2) onclick 에 indexGoodsDetail 포함 (href=javascript:; 형태)
            if not path:
                a2 = li.locator("a[onclick*='indexGoodsDetail']").first
                if a2.count() > 0:
                    path = _extract(a2.get_attribute("onclick") or "")

            # 3) href 가 javascript: 이지만 안에 URL 포함
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
    """드림몰 옵션 선택. .optSelectWrap (PC=div.radio, Mobile=label.radio) 마다
    첫 번째 라디오를 클릭하여 OnnuriGoodsOptionUtil.goodsDtlOptionClick 을 트리거.
    옵션 그룹이 여러 개면 각 그룹 모두 선택해야 alert 가 뜨지 않는다."""
    scope = page.locator(container_sel) if container_sel else page
    selected = False

    wraps = scope.locator(".optSelectWrap").all()
    for wrap in wraps:
        # 각 옵션 그룹의 첫 번째 라디오 컨테이너
        container = wrap.locator("label.radio, div.radio").first
        if container.count() == 0:
            continue
        radio = container.locator("input[type='radio']").first
        if radio.count() == 0:
            continue
        try:
            # input 이 hidden 일 수 있어 force=True
            radio.click(timeout=2000, force=True)
            selected = True
        except Exception:
            try:
                container.click(timeout=2000)
                selected = True
            except Exception:
                try:
                    radio.evaluate(
                        "el => { el.checked = true;"
                        " if (window.OnnuriGoodsOptionUtil)"
                        " OnnuriGoodsOptionUtil.goodsDtlOptionClick(el); }"
                    )
                    selected = True
                except Exception:
                    continue
        time.sleep(0.3)

    if selected:
        return True

    # 폴백: native select / radio
    try:
        opt = scope.locator("select").first
        if opt.is_visible(timeout=1000):
            opt.select_option(index=1)
            time.sleep(0.3)
            return True
    except Exception:
        pass
    try:
        radio = scope.locator("input[type='radio']").first
        if radio.is_visible(timeout=500):
            radio.check()
            time.sleep(0.3)
            return True
    except Exception:
        pass
    return False


def _pc_cart_flow(page: Page) -> tuple:
    """
    PC 흐름:
    인기상품 섹션 button.btn_cart 클릭
    → button#btnGoodsDtlCart (옵션 있으면 먼저 선택) 클릭
    → alert 처리
    """
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
    # 버튼 정보 확인
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
    time.sleep(1.5)

    # button#btnGoodsDtlCart 대기 (팝업 내)
    detail_btn = None
    for sel in DETAIL_CART_BTN_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=4000):
                detail_btn = btn
                break
        except Exception:
            continue

    if detail_btn:
        print(f"  [PC 장바구니] 상세 장바구니 버튼 발견, 옵션 선택 시도")
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
        time.sleep(2)
    else:
        print(f"  [PC 장바구니] ⚠️ 상세 장바구니 버튼을 찾을 수 없음")

    return product_name, True


def _mobile_cart_flow(page: Page, base: str) -> tuple:
    """
    Mobile 흐름 (PC 와 겹치지 않게 인기상품 두 번째 상품부터 시도):
    인기상품 섹션 상품 클릭 (상세 이동)
    → button#btnGoodsBuyLayerOpen (구매하기)
    → #layerPop-goodsOptionSelect 에서 옵션 선택 (있으면)
    → button#btnGoodsDtlCart (장바구니)
    → alert 처리
    """
    hrefs = _get_popular_hrefs(page, base)
    print(f"  [Mobile 장바구니] 인기상품 링크 {len(hrefs)}개 발견")
    assert len(hrefs) >= 1, (
        f"인기상품 링크를 찾을 수 없음 (발견 {len(hrefs)}개)"
    )

    product_name = ""
    print(f"  [Mobile 장바구니] 인기상품 {len(hrefs)}개 순회")
    for href in hrefs[:6]:
        try:
            page.goto(href, wait_until="load", timeout=15000)
            close_popups(page)
            time.sleep(0.5)
            close_popups(page)  # 한 번 더 닫기
            time.sleep(0.3)

            # 구매하기 버튼 (품절이면 없거나 숨겨짐)
            buy_btn = page.locator("button#btnGoodsBuyLayerOpen").first
            if not buy_btn.is_visible(timeout=3000):
                continue

            try:
                title_el = page.locator("h1, h2, [class*='goodsNm'], .goods-name").first
                product_name = title_el.inner_text(timeout=2000).strip()[:20]
            except Exception:
                pass

            # 구매하기 클릭 → 옵션 레이어 오픈
            print(f"  [Mobile 장바구니] 상품 '{product_name}' 구매하기 버튼 클릭 시도")
            try:
                buy_btn.click(timeout=3000)
            except Exception as e:
                print(f"  [Mobile 장바구니] click() 실패 ({str(e)[:40]}), evaluate로 재시도")
                buy_btn.evaluate("el => el.click()")
            time.sleep(1.5)

            # 옵션 레이어 내 옵션 선택
            try:
                layer = page.locator("#layerPop-goodsOptionSelect").first
                if layer.is_visible(timeout=2000):
                    wrap_cnt = page.locator(
                        "#layerPop-goodsOptionSelect .optSelectWrap"
                    ).count()
                    print(f"  [Mobile 장바구니] 옵션 레이어 발견, 옵션 그룹 {wrap_cnt}개")
                    ok_opt = _select_first_option(page, "#layerPop-goodsOptionSelect")
                    print(f"  [Mobile 장바구니] 옵션 선택 {'성공' if ok_opt else '실패/없음'}")
            except Exception:
                pass

            # 장바구니 버튼 클릭
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
                        time.sleep(2)
                        print(f"  [Mobile 장바구니] ✅ 장바구니 추가 완료")
                        return product_name, True
                except Exception:
                    continue

        except Exception:
            continue

    return product_name, False


def _select_all_cart_items(page: Page):
    """장바구니 전체선택 체크박스 체크."""
    # 스토어별 상품 체크박스 (id^='up_comp_no_checkbox')
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
            checked_any = False
            for chk in boxes:
                try:
                    if chk.is_visible(timeout=500):
                        if not chk.is_checked():
                            try:
                                chk.check(timeout=1500)
                            except Exception:
                                chk.evaluate(
                                    "el => { el.checked = true;"
                                    " el.dispatchEvent(new Event('click', {bubbles:true})); }"
                                )
                        checked_any = True
                except Exception:
                    continue
            if checked_any:
                print(f"  [주문하기] 전체선택 체크 완료 ({sel}, {len(boxes)}개)")
                time.sleep(0.3)
                return
        except Exception:
            continue
    # 폴백: JavaScript로 모든 체크박스 강제 체크
    try:
        checked = page.evaluate("""() => {
            const boxes = document.querySelectorAll('input[type="checkbox"]');
            let cnt = 0;
            boxes.forEach(cb => {
                if (!cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', {bubbles: true}));
                    cb.dispatchEvent(new Event('click', {bubbles: true}));
                }
                cnt++;
            });
            return cnt;
        }""")
        if checked:
            print(f"  [주문하기] 전체선택 JS 폴백으로 체크박스 {checked}개 처리")
            time.sleep(0.3)
    except Exception:
        pass


def _click_order_btn(page: Page) -> bool:
    """전체선택 후 주문하기 버튼을 스크롤하여 클릭. 성공 여부 반환."""
    _select_all_cart_items(page)

    for sel in ORDER_BTN_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.count() == 0:
                continue
            try:
                btn.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.3)
            except Exception:
                pass
            if not btn.is_visible(timeout=2000):
                continue
            print(f"  [주문하기] 버튼 발견 ({sel}), 클릭 시도")
            try:
                btn.click(timeout=5000)
                print(f"  [주문하기] ✅ click() 성공")
            except Exception as e:
                print(f"  [주문하기] ❌ click() 실패 ({str(e)[:40]}), evaluate로 재시도")
                btn.evaluate("el => el.click()")
                print(f"  [주문하기] ✅ evaluate click() 성공")
            return True
        except Exception:
            continue
    return False


def run(page: Page, url: str, username: str, password: str) -> str:
    base = url.replace("/main", "")
    is_mobile = "mdream" in url

    # ── dialog 핸들러: 중복 처리 방지 ───────────────────────────────────────
    def _safe_accept(d):
        try:
            print(f"  [Dialog] {d.type}: {d.message[:50]}")
            d.accept()
            print(f"  [Dialog] ✅ Accepted")
        except Exception as e:
            print(f"  [Dialog] ⚠️ Error: {str(e)[:40]}")

    page.on("dialog", _safe_accept)

    try:
        # 로그인
        ok = login(page, url, username, password)
        assert ok, "로그인 실패"

        # 사전 정리: 장바구니 비우기 (이전 실행 잔여물 제거)
        print(f"  [장바구니 사전 정리] 장바구니 비우기 시도")
        initial_count = _empty_cart(page, url)
        print(f"  [장바구니 사전 정리] 정리 후 항목 수: {initial_count}")

        # 메인으로 이동 & 인기상품 섹션 로드
        page.goto(url, wait_until="load", timeout=20000)
        close_popups(page)
        _scroll_to_popular(page)

        # ── PC / Mobile 분기 ─────────────────────────────────────────────────
        if not is_mobile:
            product_name, success = _pc_cart_flow(page)
            assert success, "인기상품 섹션에서 장바구니 담기 버튼을 찾을 수 없음"
        else:
            product_name, success = _mobile_cart_flow(page, base)
            assert success, "모바일 장바구니 담기 실패 (구매하기→장바구니 흐름 오류)"

        close_popups(page)

        # ── 장바구니 페이지 이동 및 상품 확인 ──────────────────────────────
        print(f"  [장바구니 확인] 장바구니 페이지로 이동 시도")
        _goto_cart(page, url)
        print(f"  [장바구니 확인] 현재 URL: {page.url}")

        time.sleep(1)

        item_count = _count_cart_items(page, url)
        print(f"  [장바구니 확인] 사전 {initial_count}개 → 사후 {item_count}개")

        # 사전 정리 후 카운트가 실제로 증가했는지로 검증 (false positive 방지)
        assert item_count > initial_count, (
            f"장바구니에 상품이 추가되지 않음 (사전 {initial_count}개 → 사후 {item_count}개)"
        )

        # ── 주문하기 버튼 클릭 및 결제 페이지 이동 확인 ──────────────────────
        close_popups(page)
        print(f"  [주문하기] 주문하기 버튼 클릭 시도")
        order_clicked = _click_order_btn(page)
        assert order_clicked, "주문하기 버튼을 찾을 수 없음"

        try:
            page.wait_for_url(f"**{ORDER_PAYMENT_PATH}**", timeout=10000)
        except Exception:
            pass

        current_url = page.url
        print(f"  [주문하기] 현재 URL: {current_url}")
        assert ORDER_PAYMENT_PATH in current_url, (
            f"결제 페이지로 이동 실패 (현재: {current_url})"
        )
        print(f"  [주문하기] ✅ {ORDER_PAYMENT_PATH} 이동 성공")

        # 사후 정리
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
