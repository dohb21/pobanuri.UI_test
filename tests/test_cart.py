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
    "input[type='number']",
    "input[type='checkbox'][name*='goods']",
    "input[type='checkbox'][name*='prd']",
    "input[type='checkbox'][name*='cart']",
    "input[type='checkbox'][id*='chk']",
    "[class*='cartItem']",
    "[class*='cart-item']",
    "[class*='cartPrd']",
    "[class*='cart_list'] li",
    ".orderList li",
    ".cartList li",
    "table[class*='cart'] tr:not(:first-child)",
    "[class*='goodsNm']",
    ".prd-name",
]

CART_PATHS = ["/order/indexCartList", "/cart", "/basket"]


def _goto_cart(page: Page, base_url: str):
    base = base_url.replace("/main", "")
    for path in CART_PATHS:
        try:
            page.goto(base + path, wait_until="load", timeout=15000)
            close_popups(page)
            return
        except Exception:
            continue


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
    """인기상품 섹션에서 상품 URL 목록 반환
    href 형태:
      - 일반 URL: /goods/indexGoodsDetail?goodsId=...
      - JS 형태:  javascript:gfn_baseLocationHref('/goods/indexGoodsDetail?goodsId=...')
    """
    hrefs = []
    for li in page.locator("#searchUnitList li").all()[:15]:
        try:
            a = li.locator("a[href*='indexGoodsDetail']").first
            if a.count() > 0:
                href = a.get_attribute("href") or ""
                # javascript:gfn_baseLocationHref('/goods/indexGoodsDetail?goodsId=...')
                if "javascript:" in href:
                    m = re.search(r"""['"](/[^'"]*indexGoodsDetail[^'"]*)['"]""", href)
                    href = m.group(1) if m else ""
                if href:
                    hrefs.append(href if href.startswith("http") else base + href)
        except Exception:
            continue
    return hrefs


def _select_first_option(page: Page, container_sel: str = None):
    """옵션 select 또는 radio 의 첫 번째 항목 선택"""
    loc = page.locator(container_sel) if container_sel else page
    try:
        opt = loc.locator("select").first
        if opt.is_visible(timeout=1000):
            opt.select_option(index=1)   # index 0 = "선택하세요"
            time.sleep(0.3)
            return
    except Exception:
        pass
    try:
        radio = loc.locator("input[type='radio']").first
        if radio.is_visible(timeout=500):
            radio.check()
            time.sleep(0.3)
    except Exception:
        pass


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
        _select_first_option(page)
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
    Mobile 흐름:
    인기상품 섹션 상품 클릭 (상세 이동)
    → button#btnGoodsBuyLayerOpen (구매하기)
    → #layerPop-goodsOptionSelect 에서 옵션 선택 (있으면)
    → button#btnGoodsDtlCart (장바구니)
    → alert 처리
    """
    hrefs = _get_popular_hrefs(page, base)
    assert hrefs, "인기상품에서 상품 링크를 찾을 수 없음"

    product_name = ""
    for href in hrefs[:5]:
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
                    print(f"  [Mobile 장바구니] 옵션 레이어 발견, 첫 번째 옵션 선택")
                    _select_first_option(page, "#layerPop-goodsOptionSelect")
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

        item_count = 0
        for sel in CART_ITEM_SELECTORS:
            try:
                cnt = page.locator(sel).count()
                if cnt > 0:
                    print(f"  [장바구니 확인] 셀렉터 '{sel}' 로 {cnt}개 항목 발견")
                    item_count = cnt
                    break
            except Exception:
                continue

        if item_count == 0:
            print(f"  [장바구니 확인] ⚠️ 장바구니에 항목이 없음 (모든 셀렉터 시도 완료)")

        assert item_count > 0, "장바구니에 상품이 추가되지 않음"

        # 클린업
        try:
            all_check = page.locator(
                "input[type='checkbox'][id*='all'], input[type='checkbox'][class*='all'], "
                "input[type='checkbox'][name*='all']"
            ).first
            if all_check.is_visible(timeout=2000):
                all_check.check()
                time.sleep(0.3)
            del_btn = page.locator("button:has-text('삭제'), button:has-text('선택삭제')").first
            if del_btn.is_visible(timeout=2000):
                del_btn.evaluate("el => el.click()")
                time.sleep(1)
        except Exception:
            pass

        return f"'{product_name}' 장바구니 담기 성공 (항목 {item_count}개 확인)"

    finally:
        try:
            page.remove_listener("dialog", _safe_accept)
        except Exception:
            pass
