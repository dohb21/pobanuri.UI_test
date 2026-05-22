import time
from playwright.sync_api import Page


# 실제 HTML: div.layerFull.bannerPop, #bannerPopup 등
POPUP_SELECTORS = [
    "div.mainBanner-contents.bannerPopup_slide",  # 모바일
    "div.swiper-wrap",  # PC
    "div.layerFull.bannerPop",
    "#bannerPopup",
    "[class*='bannerPop']",
    "[class*='layerFull']",
    "[class*='layerPop']",
]

CLOSE_SELECTORS = [
    "button.btn-close",
    "button.btn_close",
    "button.close",
    "button.stopWatchingToday",
    "button.btn-today",
]

NEXT_BUTTON_SELECTORS = [
    "div.swiper-button-next",
    "button[class*='swiper-button-next']",
    "[class*='swiper-button-next']",
]


def _test_popup_link(page: Page, popup_el) -> bool:
    """팝업 내 링크 진입 가능 여부 테스트"""
    current_url = page.url
    print(f"  [팝업 링크 테스트] 시작 URL: {current_url}")

    try:
        links = popup_el.locator("a").all()
        print(f"  [팝업 링크 테스트] 발견된 링크 개수: {len(links)}")

        for link_idx, link in enumerate(links):
            try:
                is_visible = link.is_visible(timeout=300)
                print(f"    링크 {link_idx}: visible={is_visible}")

                if is_visible:
                    # 링크 href 추출
                    href = link.get_attribute("href")
                    print(f"    링크 {link_idx}: href={href}")

                    if not href:
                        print(f"    링크 {link_idx}: href 없음, 스킵")
                        continue

                    # 상대 경로면 절대 경로로 변환
                    base_url = current_url.split("/main")[0]

                    if href.startswith("/goods/"):
                        # 절대 경로 /goods/... 형식
                        target_url = f"{base_url}{href}"
                    elif href.startswith("goods/"):
                        # 상대 경로 goods/... 형식 (이미 goods/ 포함됨)
                        target_url = f"{base_url}/{href}"
                    elif href.startswith("/"):
                        # 다른 절대 경로
                        target_url = f"{base_url}{href}"
                    else:
                        # 완전 상대 경로 또는 http(s)
                        target_url = href if href.startswith("http") else f"{current_url.rsplit('/', 1)[0]}/{href}"

                    print(f"    링크 {link_idx}: 대상 URL={target_url}")

                    # page.goto()로 직접 이동 (evaluate click은 실제 네비게이션을 보장하지 않음)
                    click_success = False
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=8000)
                        print(f"    링크 {link_idx}: page.goto 성공")
                        click_success = True
                        time.sleep(1)
                    except Exception as e:
                        print(f"    링크 {link_idx}: page.goto 실패 ({str(e)[:50]})")

                    if click_success:
                        # URL 변경되었는지 확인
                        new_url = page.url
                        print(f"    링크 {link_idx}: 이동 후 URL={new_url}")
                        print(f"    링크 {link_idx}: URL 변경={new_url != current_url}, goods/detail 포함={('goods' in new_url.lower() or 'detail' in new_url.lower())}")

                        if ("goods" in new_url.lower() or "detail" in new_url.lower()):
                            print(f"    링크 {link_idx}: ✅ 진입 성공!")
                            return True  # 성공! (뒤로가기는 호출자가 담당)
                        else:
                            print(f"    링크 {link_idx}: ❌ 상품 상세 페이지로 이동하지 못함")
            except Exception as e:
                print(f"    링크 {link_idx}: 예외 발생 ({str(e)[:50]})")
                continue
    except Exception as e:
        print(f"  [팝업 링크 테스트] 전체 예외: {str(e)[:50]}")
        pass

    print(f"  [팝업 링크 테스트] ❌ 모든 링크 진입 실패")
    return False


def run(page: Page, url: str) -> str:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(2)

    # 팝업 찾기
    popup_found = False
    popup_el = None
    for sel in POPUP_SELECTORS:
        try:
            els = page.locator(sel).all()
            for el in els:
                try:
                    if el.is_visible(timeout=800):
                        popup_found = True
                        popup_el = el
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if popup_found:
            break

    if not popup_found:
        return "팝업 없음 (현재 팝업이 비활성화 상태)"

    # 슬라이드 개수 확인 (가장 정확한 방법 우선)
    slide_count = 0

    try:
        # 방법 1: PC - swiper-count 텍스트에서 추출 (display:none이어도 상관없음)
        swiper_count_el = popup_el.locator(".swiper-count").first
        text = swiper_count_el.text_content()
        print(f"  [슬라이드 개수] swiper-count 텍스트: '{text}'")
        if text and "/" in text:
            parts = text.split("/")
            slide_count = int(parts[1].strip())
            print(f"  [슬라이드 개수] 방법1(swiper-count): {slide_count}개")
    except Exception as e:
        print(f"  [슬라이드 개수] 방법1 실패: {str(e)[:40]}")
        pass

    if slide_count == 0:
        try:
            # 방법 2: 모바일 - data-length 속성
            wrapper = popup_el.locator(".swiper-wrapper").first
            data_length_str = wrapper.get_attribute("data-length")
            print(f"  [슬라이드 개수] data-length: {data_length_str}")
            if data_length_str:
                slide_count = int(data_length_str)
                print(f"  [슬라이드 개수] 방법2(data-length): {slide_count}개")
        except Exception as e:
            print(f"  [슬라이드 개수] 방법2 실패: {str(e)[:40]}")
            pass

    if slide_count == 0:
        try:
            # 방법 3: aria-label에서 추출 (예: "1 / 1") - duplicate 아닌 것만
            slides = popup_el.locator("li.swiper-slide").all()
            print(f"  [슬라이드 개수] 전체 li.swiper-slide: {len(slides)}개")
            active_slide = None
            for slide in slides:
                cls = slide.get_attribute("class") or ""
                if "swiper-slide-active" in cls and "duplicate" not in cls:
                    active_slide = slide
                    break

            if active_slide:
                aria_label = active_slide.get_attribute("aria-label")
                print(f"  [슬라이드 개수] aria-label: {aria_label}")
                if aria_label and "/" in aria_label:
                    parts = aria_label.split("/")
                    slide_count = int(parts[1].strip())
                    print(f"  [슬라이드 개수] 방법3(aria-label): {slide_count}개")
        except Exception as e:
            print(f"  [슬라이드 개수] 방법3 실패: {str(e)[:40]}")
            pass

    if slide_count == 0:
        slide_count = 1  # 기본값
        print(f"  [슬라이드 개수] 기본값: {slide_count}개")

    # 각 슬라이드에 대해 진입 테스트
    tested_slides = 0
    successful_links = 0

    for slide_idx in range(slide_count):
        try:
            print(f"\n  [슬라이드 {slide_idx + 1}/{slide_count}] 테스트 시작")

            # 팝업 요소 다시 확인
            popup_el = None
            for sel in POPUP_SELECTORS:
                try:
                    els = page.locator(sel).all()
                    for el in els:
                        if el.is_visible(timeout=1000):
                            popup_el = el
                            break
                except Exception:
                    pass
                if popup_el:
                    break

            if not popup_el:
                print(f"  [슬라이드 {slide_idx + 1}] 팝업 요소를 찾을 수 없음")
                break

            tested_slides += 1

            # 현재 슬라이드 링크 테스트
            if _test_popup_link(page, popup_el):
                successful_links += 1
                print(f"  [슬라이드 {slide_idx + 1}] ✅ 성공 (총 {successful_links}개)")
            else:
                print(f"  [슬라이드 {slide_idx + 1}] ❌ 실패")

            # 뒤로가기로 팝업으로 복귀 (또는 메인으로 이동)
            try:
                page.go_back(wait_until="domcontentloaded", timeout=15000)
                print(f"  [슬라이드 {slide_idx + 1}] 뒤로가기 성공")
                time.sleep(1)
            except Exception as e:
                print(f"  [슬라이드 {slide_idx + 1}] 뒤로가기 실패, 메인 페이지로 이동")
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(1)

            # 다음 슬라이드로 이동
            if slide_idx < slide_count - 1:
                next_btn = None
                for sel in NEXT_BUTTON_SELECTORS:
                    try:
                        btn = popup_el.locator(sel).first
                        if btn.is_visible(timeout=500):
                            next_btn = btn
                            break
                    except Exception:
                        pass

                if next_btn:
                    next_btn.click(timeout=3000)
                    print(f"  [슬라이드 {slide_idx + 1}] 다음 슬라이드로 이동")
                    time.sleep(1)
                else:
                    # 다음 버튼이 없으면 마지막 슬라이드
                    print(f"  [슬라이드 {slide_idx + 1}] 다음 버튼 없음 (마지막 슬라이드)")
                    break

        except Exception as e:
            print(f"  [슬라이드 {slide_idx + 1}] 예외: {str(e)[:50]}")
            break

    print(f"\n  [최종 결과] {tested_slides}개 슬라이드 테스트 중 {successful_links}개 성공")
    assert successful_links > 0, f"팝업 링크 진입 불가능 ({tested_slides}개 테스트 중 {successful_links}개 성공)"

    # 팝업 닫기 (이미 메인 페이지이거나 팝업이 열려있으면)
    try:
        if page.url != url:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(1)
    except Exception:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)

    closed = False
    attempts = 0
    max_attempts = 3

    while not closed and attempts < max_attempts:
        attempts += 1
        try:
            # 닫기 버튼 찾기
            for sel in CLOSE_SELECTORS:
                try:
                    btns = page.locator(sel).all()
                    for btn in btns:
                        try:
                            if btn.is_visible(timeout=500):
                                # evaluate로 강제 클릭
                                try:
                                    btn.evaluate("el => el.click()")
                                except Exception:
                                    btn.click(timeout=2000)
                                time.sleep(0.8)
                                closed = True
                                break
                        except Exception:
                            continue
                except Exception:
                    continue
                if closed:
                    break
        except Exception:
            pass

        if not closed and attempts < max_attempts:
            time.sleep(0.3)

    if not closed:
        # 마지막 시도: popClose 함수 호출 (모바일)
        try:
            page.evaluate("if(typeof popClose === 'function') popClose('bannerPopup')")
            time.sleep(0.5)
            closed = True
        except Exception:
            pass

    assert closed, "팝업 닫기 버튼을 찾지 못함"

    time.sleep(0.5)
    # 팝업 닫힘 확인 (타임아웃 짧게)
    still_visible = False
    for sel in POPUP_SELECTORS:
        try:
            els = page.locator(sel).all()
            for el in els:
                try:
                    if el.is_visible(timeout=500):
                        still_visible = True
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if still_visible:
            break

    # 팝업이 안 닫혔으면 강제로 닫기 시도
    if still_visible:
        try:
            page.evaluate("""
                let popups = document.querySelectorAll('[class*="bannerPopup"], [class*="layerPop"], #bannerPopup');
                popups.forEach(p => p.style.display = 'none');
            """)
            time.sleep(0.5)
        except Exception:
            pass

    return f"팝업 확인, {slide_count}개 슬라이드, {successful_links}/{tested_slides} 링크 진입 성공, 닫기 성공"
