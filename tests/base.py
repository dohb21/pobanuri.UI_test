import os
import pathlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from playwright.sync_api import Page, Playwright


KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")

# 실제 페이지에서 확인된 팝업 닫기 버튼 선택자
POPUP_CLOSE_SELECTORS = [
    "button.btn-close",
    "button.btn_close",
    "button.close",
    "button.stopWatchingToday",
    "button.btn-today",
    "button[class*='close']",
    "a[class*='close']",
    "button[onclick*='close']",
    "div[class*='banner'] button",
    "div[class*='popup'] button",
]


@dataclass
class TestResult:
    name: str
    platform: str
    passed: bool
    error_msg: str = ""
    screenshot_path: str = ""
    note: str = ""


def _playwright_base_dirs() -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path:
        candidates.append(pathlib.Path(env_path))
    if sys.platform == "win32":
        local_app = (
            os.environ.get("LOCALAPPDATA")
            or str(pathlib.Path.home() / "AppData" / "Local")
        )
        candidates.append(pathlib.Path(local_app) / "ms-playwright")
    elif sys.platform == "darwin":
        candidates.append(pathlib.Path.home() / "Library" / "Caches" / "ms-playwright")
    else:
        candidates.append(pathlib.Path.home() / ".cache" / "ms-playwright")
    return candidates


def _find_chromium() -> str | None:
    if sys.platform == "win32":
        rel = pathlib.Path("chrome-win64") / "chrome.exe"
    elif sys.platform == "darwin":
        rel = pathlib.Path("chrome-mac") / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    else:
        rel = pathlib.Path("chrome-linux") / "chrome"

    for base in _playwright_base_dirs():
        if not base.exists():
            continue
        for entry in sorted(base.iterdir(), reverse=True):
            if entry.name.startswith("chromium-") and "headless" not in entry.name:
                chrome = entry / rel
                if chrome.exists():
                    return str(chrome)
    return None


_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def init_browser(playwright: Playwright, mobile: bool = False, record_video: bool = False, headless: bool = True):
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    }
    chromium_exe = _find_chromium()
    if chromium_exe:
        launch_kwargs["executable_path"] = chromium_exe
    browser = playwright.chromium.launch(**launch_kwargs)

    # 비디오 녹화 설정
    context_args = {}
    if record_video:
        videos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "videos")
        os.makedirs(videos_dir, exist_ok=True)
        context_args["record_video_dir"] = videos_dir

    if mobile:
        device = playwright.devices["iPhone 14 Pro Max"]
        context = browser.new_context(**device, **context_args)
    else:
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=_DESKTOP_UA,
            **context_args,
        )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page.set_default_timeout(15000)
    return browser, context, page


def close_popups(page: Page):
    """열려 있는 팝업을 모두 닫는다. 없으면 통과."""
    for sel in POPUP_CLOSE_SELECTORS:
        try:
            buttons = page.locator(sel).all()
            for btn in buttons:
                if btn.is_visible(timeout=300):
                    btn.click(timeout=1000)
        except Exception:
            continue


def login(page: Page, base_url: str, username: str, password: str, login_url: str = "") -> bool:
    """로그인. 성공 시 True."""
    if not login_url:
        login_url = base_url.replace("/main", "/indexLogin")
        # URL에 /main이 없으면 /indexLogin 경로 직접 붙이기
        if login_url == base_url:
            login_url = base_url.rstrip("/") + "/indexLogin"
    try:
        page.goto(login_url, wait_until="domcontentloaded", timeout=20000)
        close_popups(page)

        # 이미 로그인된 경우 – login 페이지가 아니면 성공으로 처리
        if "login" not in page.url.lower():
            return True

        id_input = page.locator(
            "input[name='id'], input[name='userId'], input[name='loginId'], "
            "input[name='mb_id'], input[name='loginMemberId'], "
            "input[name*='Id'], input[name*='id'][type='text'], "
            "input[placeholder*='아이디'], input[placeholder*='ID'], "
            "input[placeholder*='휴대폰'], input[placeholder*='전화번호'], "
            "input[type='tel']"
        ).first

        # 로그인 폼이 없으면 이미 로그인된 상태
        if not id_input.is_visible(timeout=5000):
            return True

        pw_input = page.locator("input[type='password']").first
        id_input.click(timeout=3000)
        id_input.fill(username)
        pw_input.click(timeout=3000)
        pw_input.fill(password)

        submitted = False

        # 1순위: fn.login() JS 직접 호출
        try:
            page.evaluate("fn.login()")
            submitted = True
        except Exception:
            pass

        # 2순위: 각종 로그인 버튼 선택자 시도
        if not submitted:
            for btn_sel in [
                "button[onclick*='fn.login']",
                "button#loginButton",
                "button.btn-basicL",
                "button[type='submit']",
                "input[type='submit']",
                "button[onclick*='login']",
                "a[onclick*='login']",
                "#loginFrm button",
                "form button[class*='login']",
                "form input[type='submit']",
            ]:
                try:
                    btn = page.locator(btn_sel).first
                    if btn.count() > 0 and btn.is_visible(timeout=1500):
                        btn.click(timeout=3000)
                        submitted = True
                        break
                except Exception:
                    continue

        # 3순위: JS form.submit()
        if not submitted:
            try:
                page.evaluate(
                    "() => { const f = document.querySelector('form'); if (f) f.submit(); }"
                )
                submitted = True
            except Exception:
                pass

        # 4순위: Enter 키
        if not submitted:
            pw_input.press("Enter")

        # 로그인 후 URL이 login 을 벗어날 때까지 대기
        try:
            page.wait_for_function(
                "() => !location.href.toLowerCase().includes('login')",
                timeout=12000
            )
            return True
        except Exception:
            pass

        # 최종 URL에 login 없으면 성공
        return "login" not in page.url.lower()
    except Exception:
        return False


def save_screenshot(page: Page, platform: str, test_name: str) -> str:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    ts = now_kst().strftime("%Y%m%d_%H%M%S")
    safe_name = test_name.replace("/", "_").replace(" ", "_")
    filename = f"{ts}_{platform}_{safe_name}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    try:
        page.screenshot(path=path, full_page=False)
    except Exception:
        pass
    return path


def run_test(name: str, platform: str, page: Page, fn, save_all_screenshots: bool = False) -> TestResult:
    try:
        note = fn(page) or ""
        result = TestResult(name=name, platform=platform, passed=True, note=str(note))
        # 성공한 경우에도 스크린샷 저장 옵션
        if save_all_screenshots:
            result.screenshot_path = save_screenshot(page, platform, name)
        return result
    except Exception as e:
        screenshot = save_screenshot(page, platform, name)
        return TestResult(
            name=name,
            platform=platform,
            passed=False,
            error_msg=str(e)[:200],
            screenshot_path=screenshot,
        )
