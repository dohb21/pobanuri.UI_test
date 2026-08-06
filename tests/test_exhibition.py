from playwright.sync_api import Page
from .base import close_popups, login


EXHIBITION_LIST_PATHS = [
    "/event/indexEvent?tab=1",
    "/event/indexExhibitionList",
    "/event/exhibitionList",
    "/exhibition/list",
]

# 기획전 상세 링크 선택자 후보
EXHBT_LINK_SELS = [
    "a[href*='indexExhibitionDetail']",
    "a[href*='exhbtNo=']",
    "a[href*='/event/detail']",
    "a[href*='/exhibition/detail']",
]


def _is_error_page(page: Page) -> tuple[bool, str]:
    try:
        content = page.content()
        for code in ["PRD0002", "PRD0003", "PRD0001"]:
            if code in content:
                return True, code
        # 에러 div/span 텍스트 탐색
        for sel in [
            ".error-code", ".errorCode", "[class*='errCode']",
            ".msg-error", "[class*='error'] p",
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    txt = (el.text_content(timeout=500) or "").strip()
                    if txt:
                        return True, txt[:30]
            except Exception:
                pass
    except Exception:
        pass
    return False, ""


def run(
    page: Page,
    url: str,
    username: str = "",
    password: str = "",
    mobile: bool = False,
) -> str:
    base = url.split("/main")[0].rstrip("/")

    # 기획전 목록 페이지 이동
    list_url = None
    for path in EXHIBITION_LIST_PATHS:
        candidate = base + path
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=15000)
            # 로그인 리다이렉트 처리
            if "login" in page.url.lower():
                if not username:
                    return "기획전: 로그인 필요 (스킵)"
                if not login(page, url, username, password):
                    return "기획전: 로그인 실패 (스킵)"
                page.goto(candidate, wait_until="domcontentloaded", timeout=15000)
            close_popups(page)
            # AJAX 로드 대기
            try:
                page.wait_for_selector("#exh_list li, a[href*='Exhibition']", timeout=6000)
            except Exception:
                pass
            # 404/에러가 아닌 목록 페이지인지 확인 (직접 URL 링크 또는 JS 호출 링크)
            has_direct = page.locator(EXHBT_LINK_SELS[0] + ", " + EXHBT_LINK_SELS[1]).count() > 0
            has_js = page.locator("a[href*='Exhibition']").count() > 0
            if has_direct or has_js:
                list_url = candidate
                break
            # 링크가 없더라도 경로가 맞으면 일단 사용
            path_key = path.split("?")[0].split("/")[-1].lower()
            if path_key and path_key in page.url.lower():
                list_url = candidate
                break
        except Exception:
            continue

    if not list_url:
        return "기획전 목록 페이지 없음 (스킵)"

    import re as _re

    # JS 함수명 → 상세 URL 경로 매핑 (PC/Mobile 모두 indexExhibitionDetail 사용)
    FUNC_PATH_MAP = {
        "openExhibitionDetail": "/event/indexExhibitionDetail",
        "openExhibitionTheme":  "/event/indexExhibitionDetail",
    }
    DEFAULT_DETAIL_PATH = "/event/indexExhibitionDetail"

    def _extract_id_and_path(text: str) -> tuple[str, str] | None:
        """'openExhibitionDetail('13702','10')' → ('13702', '/event/indexExhibitionDetail')"""
        m = _re.search(r"(open\w*[Ee]xhibition\w*)\s*\(\s*['\"]?(\d+)", text)
        if not m:
            return None
        func_name = m.group(1)
        exhbt_id = m.group(2)
        path = FUNC_PATH_MAP.get(func_name, DEFAULT_DETAIL_PATH)
        return exhbt_id, path

    # 기획전 링크 수집 (href 중복 제거) — AJAX 완료 대기
    try:
        page.wait_for_selector("#exh_list li", timeout=6000)
    except Exception:
        pass
    seen = set()
    targets = []
    try:
        # href에 직접 URL이 있는 경우
        for sel in EXHBT_LINK_SELS:
            for item in page.locator(sel).all():
                href = (item.get_attribute("href") or "").strip()
                if href and not href.startswith("javascript:") and href != "#":
                    full = href if href.startswith("http") else base + href
                    if full not in seen:
                        seen.add(full)
                        targets.append(full)

        # href="javascript:openExhibitionDetail/Theme('id','...')" 형태
        for item in page.locator("a[href*='Exhibition']").all():
            href = item.get_attribute("href") or ""
            if "javascript:" not in href:
                continue
            result = _extract_id_and_path(href)
            if result:
                exhbt_id, path = result
                full = base + f"{path}?exhbtNo={exhbt_id}"
                if full not in seen:
                    seen.add(full)
                    targets.append(full)

        # onclick 기반
        for item in page.locator("a[onclick*='Exhibition']").all():
            onclick = item.get_attribute("onclick") or ""
            result = _extract_id_and_path(onclick)
            if result:
                exhbt_id, path = result
                full = base + f"{path}?exhbtNo={exhbt_id}"
                if full not in seen:
                    seen.add(full)
                    targets.append(full)
    except Exception:
        pass

    if not targets:
        return "기획전 항목 없음 (스킵)"

    print(f"\n  [기획전] 총 {len(targets)}건 확인 시작")
    error_items = []
    ok_count = 0

    for i, target in enumerate(targets):
        try:
            page.goto(target, wait_until="domcontentloaded", timeout=15000)
            close_popups(page)
            is_err, code = _is_error_page(page)
            if is_err:
                error_items.append(f"[{i+1}] {code} ({target.split('?')[-1]})")
                print(f"  [기획전] ❌ [{i+1}/{len(targets)}] {code}: {target}")
            else:
                ok_count += 1
                print(f"  [기획전] ✅ [{i+1}/{len(targets)}] 정상")
        except Exception as e:
            error_items.append(f"[{i+1}] 접근 실패: {str(e)[:40]}")
            print(f"  [기획전] ❌ [{i+1}/{len(targets)}] 접근 실패: {str(e)[:40]}")

    summary = f"기획전 {ok_count}/{len(targets)}건 정상"
    if error_items:
        raise AssertionError(f"{summary} | 오류: " + "; ".join(error_items))
    return summary
