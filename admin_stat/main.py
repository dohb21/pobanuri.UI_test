import base64
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

import requests as _req
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tabulate import tabulate

from chart_builder import draw_combined_a5, draw_report_image
from report import (
    build_html_report,
    build_report_image_html, send_email,
    build_kakao_text, send_kakao,
)
from report.sales import build_sales_email_html, attach_excel

load_dotenv()

BASE_URL = "https://dreamadmin.onuri.co.kr"
MAIN_URL = f"{BASE_URL}/main/mainView.do"

USERNAME = os.getenv("ADMIN_USER", "")
PASSWORD = os.getenv("ADMIN_PASS", "")
USER_FIELD = os.getenv("LOGIN_USER_FIELD", "")
PASS_FIELD = os.getenv("LOGIN_PASS_FIELD", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "reports")

# 자동 탐지 순서 (env 미지정 시)
_USER_CANDIDATES = ["loginId", "userId", "adminId", "id", "username"]
_PASS_CANDIDATES = ["loginPw", "userPwd", "adminPw", "pw", "password"]


def setup_driver(headless: bool = True) -> webdriver.Chrome:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=ko-KR")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def find_field(driver, candidates: list[str]):
    for name in candidates:
        try:
            return driver.find_element(By.NAME, name)
        except NoSuchElementException:
            continue
    return None


def dismiss_alert(driver: webdriver.Chrome) -> None:
    try:
        alert = driver.switch_to.alert
        alert.accept()
    except Exception:
        pass


def do_login(driver: webdriver.Chrome, wait: WebDriverWait, debug: bool = False) -> None:
    driver.get(MAIN_URL)
    time.sleep(2)
    dismiss_alert(driver)  # "세션이 종료 되었습니다." 등 팝업 처리

    if debug:
        print(f"[디버그] 현재 URL: {driver.current_url}")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"[디버그] 발견된 input 필드:")
        for inp in inputs:
            print(f"  type={inp.get_attribute('type')!r:10}  name={inp.get_attribute('name')!r:20}  id={inp.get_attribute('id')!r}")

    if "mainView" in driver.current_url:
        return

    user_field = (
        driver.find_element(By.NAME, USER_FIELD) if USER_FIELD
        else find_field(driver, _USER_CANDIDATES)
    )
    pass_field = (
        driver.find_element(By.NAME, PASS_FIELD) if PASS_FIELD
        else find_field(driver, _PASS_CANDIDATES)
    )

    if not user_field or not pass_field:
        raise RuntimeError(
            "로그인 폼 필드를 찾지 못했습니다.\n"
            ".env에 LOGIN_USER_FIELD, LOGIN_PASS_FIELD를 직접 지정하세요."
        )

    if debug:
        print(f"[디버그] 사용할 필드: user={user_field.get_attribute('name')!r}, pass={pass_field.get_attribute('name')!r}")

    user_field.clear()
    user_field.send_keys(USERNAME)
    pass_field.clear()
    pass_field.send_keys(PASSWORD)

    # 로그인 버튼 클릭 — CSS 셀렉터 → XPath 텍스트 순으로 탐색
    submit_btn = None
    css_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button.btnLogin",
        "a.btnLogin",
        ".btn-login",
    ]
    for selector in css_selectors:
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
            break
        except NoSuchElementException:
            continue

    if not submit_btn:
        xpath_candidates = [
            "//button[contains(., '로그인')]",
            "//a[contains(., '로그인')]",
            "//input[@type='button' and contains(@value, '로그인')]",
            "//button",  # 최후 수단: 페이지 첫 번째 button
        ]
        for xp in xpath_candidates:
            try:
                submit_btn = driver.find_element(By.XPATH, xp)
                break
            except NoSuchElementException:
                continue

    if submit_btn:
        if debug:
            print(f"[디버그] 버튼 클릭: <{submit_btn.tag_name}> text={submit_btn.text!r}")
        submit_btn.click()
    else:
        if debug:
            print("[디버그] 버튼을 못 찾아 form.submit() 사용")
        pass_field.submit()

    time.sleep(2)
    dismiss_alert(driver)

    if debug:
        print(f"[디버그] 제출 후 URL: {driver.current_url}")
        print(f"[디버그] 페이지 제목: {driver.title}")
        # 페이지에 오류 메시지가 있으면 출력
        from bs4 import BeautifulSoup as _BS
        _soup = _BS(driver.page_source, "html.parser")
        for sel in [".error", ".msg-error", ".login-error", "#errMsg", ".alert"]:
            el = _soup.select_one(sel)
            if el and el.get_text(strip=True):
                print(f"[디버그] 오류 메시지 ({sel}): {el.get_text(strip=True)}")

    try:
        wait.until(EC.url_contains("mainView"))
    except TimeoutException:
        raise RuntimeError(
            f"로그인 실패.\n"
            f"현재 URL: {driver.current_url}\n"
            "아이디/비밀번호 또는 VPN 연결을 확인하세요."
        )


def _cookies(driver: webdriver.Chrome) -> dict:
    return {c["name"]: c["value"] for c in driver.get_cookies()}


def _api_headers() -> dict:
    return {"Referer": MAIN_URL, "X-Requested-With": "XMLHttpRequest"}


# ── Summary 테이블: requests로 API 직접 호출 ──────────────────────────────────

def fetch_summary_table(driver: webdriver.Chrome):
    resp = _req.post(
        f"{BASE_URL}/main/totalStatReportGrid.do",
        headers=_api_headers(),
        cookies=_cookies(driver),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    today = datetime.now(KST)
    col_headers = ["구분",
                   (today - timedelta(days=3)).strftime("%m/%d"),
                   (today - timedelta(days=2)).strftime("%m/%d"),
                   (today - timedelta(days=1)).strftime("%m/%d(전일)"),
                   "당월 누적"]

    def _monthly_excl_today(row):
        try:
            da = int(row.get("daTotal", 0) or 0)
            d0 = int(row.get("d0Total", 0) or 0)
            return str(da - d0)
        except (ValueError, TypeError):
            return str(row.get("daTotal", ""))

    keys = ["name", "d3Total", "d2Total", "d1Total"]
    raw_rows = data.get("rows", [])
    monthly_by_name = {row.get("name"): _monthly_excl_today(row) for row in raw_rows}

    rows = []
    for row in raw_rows:
        name = row.get("name")
        # 누적회원은 신규회원의 당월 누적 계산값을 그대로 사용
        monthly = monthly_by_name.get("신규회원", "") if name == "누적회원" else monthly_by_name[name]
        rows.append([str(row.get(k, "")) for k in keys] + [monthly])

    return col_headers, rows



def _parse_ul_from_soup(soup, ul_id: str) -> list[tuple[str, str]]:
    ul = soup.select_one(f"#{ul_id}")
    if not ul:
        return []
    result = []
    for li in ul.select("li"):
        num = li.select_one(".listNum")
        anc = li.select_one(".anc")
        if num and anc:
            result.append((num.get_text(strip=True), anc.get_text(strip=True)))
    return result


def _selenium_read_list(driver: webdriver.Chrome, css: str) -> list[tuple[str, str]]:
    items = driver.find_elements(By.CSS_SELECTOR, css)
    result = []
    for li in items:
        try:
            num = li.find_element(By.CLASS_NAME, "listNum").text.strip()
            anc = li.find_element(By.CLASS_NAME, "anc").text.strip()
            if num and anc:
                result.append((num, anc))
        except NoSuchElementException:
            continue
    return result


def fetch_lists_from_page(driver: webdriver.Chrome, debug: bool = False) -> tuple[list, list]:
    # API를 직접 호출하여 데이터 수집
    top5 = []
    top10 = []

    try:
        # TOP 5 상품 (getGoodsSearchTop10.do)
        resp_goods = _req.get(
            f"{BASE_URL}/main/getGoodsSearchTop10.do",
            headers=_api_headers(),
            cookies=_cookies(driver),
            timeout=15,
        )
        resp_goods.raise_for_status()
        goods_data = resp_goods.json()

        # goods_data에서 realTimeList 추출
        if isinstance(goods_data, dict) and "realTimeList" in goods_data:
            real_time_list = goods_data["realTimeList"]
            for idx, item in enumerate(real_time_list[:5], 1):  # 최대 5개만
                goods_name = item.get("goodsInfoStr", "")
                if goods_name:
                    top5.append((str(idx), goods_name))

        if debug:
            print(f"[디버그] getGoodsSearchTop10.do → {len(top5)}개 파싱")

    except Exception as e:
        if debug:
            print(f"[디버그] getGoodsSearchTop10.do 실패: {e}")

    try:
        # TOP 10 검색키워드 (getTrendkeywordsBo.do)
        resp_keywords = _req.get(
            f"{BASE_URL}/main/getTrendkeywordsBo.do",
            headers=_api_headers(),
            cookies=_cookies(driver),
            timeout=15,
        )
        resp_keywords.raise_for_status()
        keywords_data = resp_keywords.json()

        # keywords_data에서 rankList 추출
        if isinstance(keywords_data, dict) and "rankList" in keywords_data:
            rank_list = keywords_data["rankList"]
            for idx, keyword in enumerate(rank_list[:10], 1):  # 최대 10개
                if keyword:
                    top10.append((str(idx), str(keyword)))

        if debug:
            print(f"[디버그] getTrendkeywordsBo.do → {len(top10)}개 파싱")

    except Exception as e:
        if debug:
            print(f"[디버그] getTrendkeywordsBo.do 실패: {e}")

    if debug:
        print(f"[디버그] 최종 결과 → top5={len(top5)}건, top10={len(top10)}건")

    return top5, top10




def _parse_csv_ints(s: str) -> list[int]:
    return [int(v.strip()) for v in s.split(",") if v.strip()]


def _parse_csv_floats(s: str) -> list[float]:
    return [float(v.strip()) for v in s.split(",") if v.strip()]


def _parse_csv_strs(s: str) -> list[str]:
    return [v.strip() for v in s.split(",") if v.strip()]



def fetch_order_chart_data(driver: webdriver.Chrome) -> dict | None:
    try:
        resp = _req.post(
            f"{BASE_URL}/main/getOrderChart.do",
            headers=_api_headers(),
            cookies=_cookies(driver),
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        dates = _parse_csv_strs(raw.get("dt", ""))
        if not dates:
            return None
        return {
            "dates":    dates,
            "orderAmt": _parse_csv_ints(raw.get("orderAmt", "")),
            "canAmt":   _parse_csv_ints(raw.get("canAmt",   "")),
            "retAmt":   _parse_csv_ints(raw.get("retAmt",   "")),
            "orderCnt": _parse_csv_ints(raw.get("orderCnt", "")),
            "canCnt":   _parse_csv_ints(raw.get("canCnt",   "")),
            "retCnt":   _parse_csv_ints(raw.get("retCnt",   "")),
        }
    except Exception:
        return None


def fetch_claim_chart_data(driver: webdriver.Chrome) -> dict | None:
    try:
        resp = _req.post(
            f"{BASE_URL}/main/getClaimBarChart.do",
            headers=_api_headers(),
            cookies=_cookies(driver),
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        # API가 배열 형태로 반환하는 경우: [{"dashSp": "기타", "dashRate": "100"}, ...]
        if isinstance(raw, list):
            labels = [item.get("dashSp", "") for item in raw if item.get("dashSp")]
            rates  = [float(item.get("dashRate", 0)) for item in raw if item.get("dashSp")]
        else:
            labels = _parse_csv_strs(raw.get("dashSp",   ""))
            rates  = _parse_csv_floats(raw.get("dashRate", ""))
        if not labels or not rates:
            return None
        return {"labels": labels, "rates": rates}
    except Exception:
        return None


def fetch_order_claim_charts(
    driver: webdriver.Chrome, timestamp: str, output_dir: str, debug: bool = False,
) -> tuple[dict, dict | None, dict | None]:
    """주문/클레임 차트를 A5 단일 이미지로 생성. (chart_paths, order_data, claim_data) 반환"""
    chart_dir = os.path.join(output_dir, "charts")
    os.makedirs(chart_dir, exist_ok=True)

    order_data = fetch_order_chart_data(driver)
    if not order_data:
        if debug:
            print("[디버그] getOrderChart.do 데이터 없음")
        return {}, None, None

    claim_data = fetch_claim_chart_data(driver)
    if debug and not claim_data:
        print("[디버그] getClaimBarChart.do 데이터 없음 (클레임 없음)")

    fpath = os.path.join(chart_dir, f"{timestamp}_charts.png")
    if draw_combined_a5(order_data, claim_data, fpath):
        if debug:
            print(f"[디버그] 통합 차트 → {fpath}")
        return {"charts": fpath}, order_data, claim_data
    return {}, order_data, claim_data


def save_html_as_pdf(driver: webdriver.Chrome, html_content: str, pdf_path: str) -> None:
    """HTML 문자열을 A4 PDF로 변환 — 임시 HTML 파일 사용 후 삭제"""
    import tempfile
    pdf_dir = os.path.dirname(os.path.abspath(pdf_path))
    os.makedirs(pdf_dir, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", encoding="utf-8",
            delete=False, dir=pdf_dir
        ) as f:
            f.write(html_content)
            tmp_path = f.name

        abs_html = tmp_path.replace("\\", "/")
        driver.get(f"file:///{abs_html}")
        time.sleep(1)

        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "paperWidth": 8.27,
            "paperHeight": 11.69,
            "marginTop": 0.4,
            "marginBottom": 0.4,
            "marginLeft": 0.4,
            "marginRight": 0.4,
            "printBackground": True,
            "displayHeaderFooter": False,
            "preferCSSPageSize": False,
            "scale": 0.8,
        })

        pdf_data = base64.b64decode(result["data"])
        with open(pdf_path, "wb") as f:
            f.write(pdf_data)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── 매출 통계 설정 ───────────────────────────────────────────────────────────
_B2C_BASE = BASE_URL                                        # B2C 어드민
_B2B_BASE = "https://admin2410.pobaonuri.kr"                # B2B 어드민
_SALES_PATH = "/statistics/salesStatsGrid.do"


def _sales_period(period_type: str):
    """KST 기준 직전 주/월 기간 반환 (start, end) — date 객체
    weekly: 실행 요일과 무관하게 직전 주 월~일
    monthly: 실행 일자와 무관하게 직전 달 1일~말일
    """
    today = datetime.now(KST).date()
    if period_type == "weekly":
        # 이번 주 월요일 = today - weekday (월=0)
        this_monday = today - timedelta(days=today.weekday())
        end   = this_monday - timedelta(days=1)   # 직전 주 일요일
        start = this_monday - timedelta(days=7)   # 직전 주 월요일
    else:
        first = today.replace(day=1)
        end   = first - timedelta(days=1)   # 전월 말일
        start = end.replace(day=1)          # 전월 1일
    return start, end


def _b2b_login_selenium(driver: webdriver.Chrome) -> dict | None:
    """Selenium으로 B2B 어드민 로그인 후 쿠키 dict 반환. 실패 시 None."""
    b2b_user = os.getenv("B2B_ADMIN_USER", "")
    b2b_pass = os.getenv("B2B_ADMIN_PASS", "")
    if not b2b_user or not b2b_pass:
        print("[B2B] B2B_ADMIN_USER / B2B_ADMIN_PASS 설정 필요")
        return None

    original_url = driver.current_url
    try:
        driver.get(f"{_B2B_BASE}/main/mainView.do")
        time.sleep(2)
        dismiss_alert(driver)

        if "mainView" in driver.current_url:
            print("[B2B] 로그인 성공")
            return _cookies(driver)

        user_el = find_field(driver, _USER_CANDIDATES)
        pass_el = find_field(driver, _PASS_CANDIDATES)
        if not user_el or not pass_el:
            print(f"[B2B] 로그인 폼 필드 미발견 (현재 URL: {driver.current_url})")
            return None

        user_el.clear(); user_el.send_keys(b2b_user)
        pass_el.clear(); pass_el.send_keys(b2b_pass)

        submit_btn = None
        for sel in ["button[type='submit']", "input[type='submit']",
                    "button.btnLogin", ".btn-login"]:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, sel)
                break
            except NoSuchElementException:
                continue
        if not submit_btn:
            for xp in ["//button[contains(.,'로그인')]", "//button"]:
                try:
                    submit_btn = driver.find_element(By.XPATH, xp)
                    break
                except NoSuchElementException:
                    continue
        if submit_btn:
            submit_btn.click()
        else:
            from selenium.webdriver.common.keys import Keys
            pass_el.send_keys(Keys.RETURN)

        time.sleep(3)
        dismiss_alert(driver)

        if "mainView" not in driver.current_url:
            print(f"[B2B] 로그인 실패 (URL: {driver.current_url})")
            return None

        print("[B2B] 로그인 성공")
        return _cookies(driver)
    except Exception as e:
        print(f"[B2B 로그인 예외] {e}")
        return None
    finally:
        driver.get(original_url)
        time.sleep(1)


_SALES_EXCEL_PATH = "/statistics/salesStatsExcelDownload.do"


def _call_sales_api(session, base_url: str, start, end,
                    gbc: str, period_type: str) -> list[dict]:
    """salesStatsGrid.do 호출 → parsed rows 반환 (jqGrid 전체 파라미터 세트 사용)"""
    from report.sales import parse_sales_rows
    period_code = "WEEK" if period_type == "weekly" else "MONTH"
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")
    try:
        resp = session.post(
            f"{base_url}{_SALES_PATH}",
            data={
                "startDt":       start_str,
                "endDt":         end_str,
                "startDt1":      start_str,
                "endDt1":        end_str,
                "gbCd":          gbc,
                "periodType":    period_code,
                "stId":          "",
                "stIdSelectRaw": "",
                "_search":       "false",
                "nd":            str(int(time.time() * 1000)),
                "rows":          "-1",
                "page":          "1",
                "sidx":          "periodNm asc, periodNm",
                "sord":          "desc",
            },
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        items = body.get("data", [])
        print(f"[DEBUG {gbc}] 응답 행 수: {len(items)}, 첫 행: {items[0] if items else '없음'}")
        return parse_sales_rows(items)
    except Exception as e:
        print(f"[매출통계] API 실패 ({base_url}, gbCd={gbc}): {e}")
        return []


def _download_b2b_excel(session, base_url: str, start, end,
                        period_type: str, filepath: str) -> bool:
    """B2B 몰별 엑셀 다운로드 버튼과 동일한 엔드포인트 호출 → 파일 저장"""
    period_code = "WEEK" if period_type == "weekly" else "MONTH"
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")
    try:
        resp = session.post(
            f"{base_url}{_SALES_EXCEL_PATH}",
            data={
                "startDt":       start_str,
                "endDt":         end_str,
                "startDt1":      start_str,
                "endDt1":        end_str,
                "gbCd":          "B2B_SITE",
                "periodType":    period_code,
                "stId":          "",
                "stIdSelectRaw": "",
            },
            timeout=30,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "excel" in content_type or "spreadsheet" in content_type or "octet-stream" in content_type:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"[B2B] 엑셀 다운로드 완료: {filepath}")
            return True
        else:
            print(f"[B2B] 엑셀 다운로드 실패 — Content-Type: {content_type}, 응답: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[B2B] 엑셀 다운로드 예외: {e}")
        return False


def fetch_sales_stats(driver: webdriver.Chrome, period_type: str):
    """B2C + B2B 매출 통계 수집. (b2c_rows, b2b_rows, start, end) 반환"""
    start, end = _sales_period(period_type)

    # B2C: selenium 쿠키를 requests에 넘겨 직접 호출
    cookies = _cookies(driver)

    _sales_headers = {
        "Referer": f"{_B2C_BASE}/statistics/salesStatsView.do",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": _B2C_BASE,
    }

    class _B2CSess:
        def post(self, url, data=None, timeout=15, **kw):
            resp = _req.post(url, data=data, headers=_sales_headers,
                             cookies=cookies, timeout=timeout)
            if not resp.ok:
                print(f"[B2C 응답 {resp.status_code}] {resp.text[:500]}")
            return resp

    b2c_rows = _call_sales_api(_B2CSess(), _B2C_BASE, start, end, "B2C", period_type)

    # B2B: B2C와 동일하게 selenium으로 로그인 후 쿠키를 requests에 사용
    b2b_cookies = _b2b_login_selenium(driver)
    b2b_sess = None
    b2b_base = _B2B_BASE
    if b2b_cookies:
        b2b_headers = {
            "Referer": f"{_B2B_BASE}/statistics/salesStatsView.do",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": _B2B_BASE,
        }

        class _B2BSess:
            def post(self, url, data=None, timeout=15, **kw):
                resp = _req.post(url, data=data, headers=b2b_headers,
                                 cookies=b2b_cookies, timeout=timeout)
                if not resp.ok:
                    print(f"[B2B 응답 {resp.status_code}] {resp.text[:500]}")
                return resp

        b2b_sess = _B2BSess()
        b2b_rows = _call_sales_api(b2b_sess, b2b_base, start, end, "B2B_TOTAL", period_type)
        print(f"[B2B] TOTAL {len(b2b_rows)}행")
    else:
        b2b_rows = []

    return b2c_rows, b2b_rows, b2b_sess, b2b_base, start, end


def send_sales_report(driver: webdriver.Chrome, period_type: str) -> None:
    """매출 통계 이메일 조합 및 발송"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    label = "주간" if period_type == "weekly" else "월간"
    print(f"\n매출 통계 {label} 리포트 생성 중...")

    b2c_rows, b2b_rows, b2b_sess, b2b_base, start, end = fetch_sales_stats(driver, period_type)

    if not b2c_rows and not b2b_rows:
        print(f"[매출통계] 데이터 없음 — {label} 발송 스킵")
        return

    html = build_sales_email_html(period_type, start, end, b2c_rows, b2b_rows)

    # B2B 몰별 엑셀 다운로드
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str   = datetime.now(KST).strftime("%Y%m%d")
    excel_path = os.path.join(OUTPUT_DIR, f"B2B_매출통계_{date_str}.xlsx")
    excel_ok   = False
    if b2b_sess:
        excel_ok = _download_b2b_excel(b2b_sess, b2b_base, start, end, period_type, excel_path)
    else:
        print("[매출통계] B2B 세션 없음 — Excel 첨부 생략")

    period_ko = f"{start.strftime('%m월 %d일')}~{end.strftime('%m월 %d일')}"
    subject   = f"[온누리몰] {label} 매출 통계 - {start.strftime('%Y년')} {period_ko}"

    sales_to = [a.strip() for a in
                os.getenv("SALES_EMAIL_TO", os.getenv("EMAIL_TO", "")).split(",")
                if a.strip()]
    if not sales_to:
        print("[매출통계] 수신자 없음 (SALES_EMAIL_TO 또는 EMAIL_TO 설정 필요)")
        return

    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    from_addr = os.getenv("EMAIL_FROM", "")
    password  = os.getenv("EMAIL_PASSWORD", "")

    if not from_addr or not password:
        print("[매출통계] 이메일 설정 없음")
        return

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(sales_to)
    msg.attach(MIMEText(html, "html", "utf-8"))

    if excel_ok:
        attach_excel(msg, excel_path, os.path.basename(excel_path))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as srv:
            srv.ehlo(); srv.starttls()
            srv.login(from_addr, password)
            srv.sendmail(from_addr, sales_to, msg.as_bytes())
        print(f"매출통계 {label} 이메일 발송 완료 → {', '.join(sales_to)}")
    except Exception as e:
        print(f"매출통계 {label} 이메일 발송 실패: {e}")


def main() -> None:
    if not USERNAME or not PASSWORD:
        print("오류: .env 파일에 ADMIN_USER와 ADMIN_PASS를 설정하세요.")
        sys.exit(1)

    debug    = "--debug" in sys.argv
    headless = "--show" not in sys.argv
    force_weekly  = "--sales-weekly"  in sys.argv
    force_monthly = "--sales-monthly" in sys.argv

    driver = setup_driver(headless=headless)
    wait = WebDriverWait(driver, 25)

    try:
        print("로그인 중...")
        do_login(driver, wait, debug=debug)
        # 페이지 DOM 로드 완료 대기 (API 호출에 필요한 세션 쿠키 확보)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(5)  # easyui 초기화 및 JS 함수 등록 대기

        timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")

        sales_only = force_weekly or force_monthly

        # ── 매출 통계 이메일 (--sales-weekly / --sales-monthly 플래그) ──────────
        if sales_only:
            today_kst = datetime.now(KST)
            if force_weekly:
                send_sales_report(driver, "weekly")
            if force_monthly:
                send_sales_report(driver, "monthly")
        else:
            print("Summary 데이터 수집 중...")
            headers, rows = fetch_summary_table(driver)

            print("상품/키워드 데이터 수집 중...")
            top5, top10 = fetch_lists_from_page(driver, debug=debug)

            print("주문/클레임 차트 생성 중...")
            chart_paths_abs, order_data, claim_data = fetch_order_claim_charts(
                driver, timestamp, OUTPUT_DIR, debug=debug
            )
            chart_paths = {
                k: os.path.relpath(v, OUTPUT_DIR).replace("\\", "/")
                for k, v in chart_paths_abs.items()
            }

            # 카카오톡 전송용 리포트 이미지 생성
            kakao_img_path = os.path.join(OUTPUT_DIR, "charts", f"{timestamp}_kakao.png")
            kakao_ok = draw_report_image(
                headers, rows, top5, top10, order_data, claim_data, kakao_img_path
            )
            if not kakao_ok:
                kakao_img_path = None

            # PDF 생성
            html_report = build_html_report(headers, rows, top5, top10, chart_paths=chart_paths)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            pdf_path = os.path.join(OUTPUT_DIR, f"dream_{timestamp[:8]}.pdf")
            print("PDF 생성 중...")
            try:
                save_html_as_pdf(driver, html_report, pdf_path)
                print(f"리포트 생성 완료: {pdf_path}")
            except Exception as e:
                print(f"PDF 생성 실패: {e}")

            # ── 매출 통계 이메일 (스케줄: 월요일=주간, 매달 1일=월간) ──────────
            today_kst = datetime.now(KST)
            if today_kst.weekday() == 0:
                send_sales_report(driver, "weekly")
            if today_kst.day == 1:
                send_sales_report(driver, "monthly")

            today_str = (datetime.now(KST) - timedelta(days=1)).strftime("%Y년 %m월 %d일")

            # ── 일일 Admin 통계 이메일 ────────────────────────────────────────
            email_to = [a.strip() for a in os.getenv("EMAIL_TO", "").split(",") if a.strip()]
            if email_to:
                print("\n이메일 발송 중...")
                email_html = build_report_image_html()
                ok = send_email(
                    subject=f"[드림몰] Admin 통계 리포트 - {today_str}",
                    html_body=email_html,
                    to_addrs=email_to,
                    chart_paths={"report": kakao_img_path} if kakao_img_path else {},
                )
                print(f"{'이메일 발송 완료' if ok else '이메일 발송 실패'} → {', '.join(email_to)}")

            # ── 카카오톡 발송 ─────────────────────────────────────────────────
            kakao_to = [n.strip() for n in os.getenv("KAKAO_TO", "").split(",") if n.strip()]
            if kakao_to:
                print("\n카카오톡 발송 중...")
                kakao_text = build_kakao_text(headers, rows, top5, top10)
                ok = send_kakao(kakao_text, kakao_to, image_path=kakao_img_path)
                print(f"{'카카오톡 발송 완료' if ok else '카카오톡 발송 실패'} → {', '.join(kakao_to)}")

        # 두레이로 발송
        # dooray_config = get_dooray_config()
        # if dooray_config and dooray_config.get("webhook_url"):
        #     print("\n두레이 메신저로 발송 중...")
        #     success = send_to_dooray(
        #         dooray_message,
        #         dooray_config["webhook_url"],
        #         dooray_config.get("bot_name", "Admin 통계봇"),
        #     )
        #     if success:
        #         print("두레이 메신저 발송 완료!")
        #     else:
        #         print("두레이 메신저 발송 실패")
        # else:
        #     print("\n두레이 설정이 없습니다. (config.yml 확인)")


    except RuntimeError as e:
        print(f"\n오류: {e}")
        sys.exit(1)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
