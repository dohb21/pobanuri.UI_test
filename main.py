import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import time
import random
import yaml
import concurrent.futures
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

from tests.base import KST, TestResult, init_browser, run_test, login, now_kst
from tests import test_main, test_popup, test_search, test_category, test_gnb, test_popular, test_cart, test_shipping
from report.generator import build_report, build_simple_message
from report.dooray import send as dooray_send

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_platform(playwright, mall: dict, cfg: dict, mobile: bool, headless: bool = True) -> list[TestResult]:
    mall_name = mall["name"]
    platform_label = f"{mall_name} {'Mobile' if mobile else 'PC'}"
    url = mall["urls"]["mobile"] if mobile else mall["urls"]["pc"]
    requires_login = mall.get("requires_login", False)
    explicit_login_url = mall.get("login_url", "")

    username = os.environ.get("ID", "")
    password = os.environ.get("PASSWORD", "")
    valid_kws = cfg["search"]["valid"]
    cat_pool = mall.get("categories") or cfg["categories"]["pool"]
    cat_count = cfg["categories"]["count"]

    results = []
    browser, context, page = init_browser(playwright, mobile=mobile, headless=headless)

    try:
        # 로그인이 필요한 몰: 테스트 시작 전 로그인
        if requires_login and username:
            print(f"  [로그인] {mall_name} 로그인 시도...", end=" ", flush=True)
            ok = login(page, url, username, password, login_url=explicit_login_url)
            print("[완료]" if ok else "[실패] 로그인 실패, 계속 진행")

        # 1. 메인 화면 진입
        print(f"  [1/8] 메인 화면 진입...", end=" ", flush=True)
        result = run_test("메인 화면 진입", platform_label, page,
                         lambda p: test_main.run(p, url))
        results.append(result)
        print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")

        # 2. 메인 팝업 (비디오 녹화 + 스크린샷)
        print(f"  [2/8] 메인 팝업 노출...", end=" ", flush=True)
        browser2, ctx2, page2 = init_browser(playwright, mobile=mobile, record_video=True, headless=headless, block_resources=False)
        try:
            if requires_login and username:
                login(page2, url, username, password, login_url=explicit_login_url)
            result = run_test("메인 팝업 노출", platform_label, page2,
                            lambda p: test_popup.run(p, url), save_all_screenshots=True)
            results.append(result)
            print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")
        finally:
            browser2.close()

        # 3. 검색
        print(f"  [3/8] 검색 기능...", end=" ", flush=True)
        result = run_test("검색 기능", platform_label, page,
                         lambda p: test_search.run(p, url, valid_kws))
        results.append(result)
        print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")

        # 4. 카테고리
        print(f"  [4/8] 카테고리 상품 노출...", end=" ", flush=True)
        result = run_test("카테고리 상품 노출", platform_label, page,
                         lambda p: test_category.run(p, url, cat_pool, cat_count, mobile))
        results.append(result)
        print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")

        # 5. GNB 메뉴
        print(f"  [5/8] GNB 메뉴 진입...", end=" ", flush=True)
        result = run_test("GNB 메뉴 진입", platform_label, page,
                         lambda p: test_gnb.run(p, url, username, password, mobile=mobile))
        results.append(result)
        print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")

        # 6. 인기상품
        print(f"  [6/8] 하단 인기상품 목록...", end=" ", flush=True)
        result = run_test("하단 인기상품 목록", platform_label, page,
                         lambda p: test_popular.run(p, url))
        results.append(result)
        print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")

        # 7. 장바구니 (계정이 있을 때만)
        if username:
            print(f"  [7/8] 장바구니 담기...", end=" ", flush=True)
            result = run_test("장바구니 담기", platform_label, page,
                            lambda p: test_cart.run(p, url, username, password, mobile=mobile))
            results.append(result)
            print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")
        else:
            print(f"  [7/8] 장바구니 담기... ⊘ (계정 없음)")

        # 8. 배송지 등록 (계정이 있을 때만)
        if username:
            print(f"  [8/8] 배송지 등록 양식...", end=" ", flush=True)
            result = run_test("배송지 등록 양식", platform_label, page,
                            lambda p: test_shipping.run(p, url, username, password))
            results.append(result)
            print("[완료]" if result.passed else f"[실패] {result.error_msg[:30]}")
        else:
            print(f"  [8/8] 배송지 등록 양식... ⊘ (계정 없음)")

    finally:
        browser.close()

    return results


def _run_mall_worker(args: tuple) -> list[TestResult]:
    """각 몰을 독립 프로세스에서 실행하는 워커 함수."""
    mall, cfg, headless = args
    # 자식 프로세스에서 인코딩 및 환경변수 재설정
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

    mall_name = mall["name"]
    all_results = []
    with sync_playwright() as playwright:
        for mobile in [False, True]:
            label = "Mobile" if mobile else "PC"
            print(f"\n[{mall_name} / {label}] 테스트 시작...", flush=True)
            print("-" * 50, flush=True)
            results = run_platform(playwright, mall, cfg, mobile=mobile, headless=headless)
            all_results += results
            passed = sum(1 for r in results if r.passed)
            print(f"{mall_name} {label} 완료: {passed}/{len(results)} 통과", flush=True)
    return all_results


def run_all(cfg: dict, headless: bool = True) -> list[TestResult]:
    malls = [m for m in cfg.get("malls", []) if not m.get("skip", False)]
    args_list = [(mall, cfg, headless) for mall in malls]

    all_results = []
    # 몰별 병렬 실행: 4개 몰이 동시에 실행되어 총 소요 시간 ≈ 가장 느린 몰 1개 기준
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(malls)) as executor:
        futures = {executor.submit(_run_mall_worker, args): args[0]["name"] for args in args_list}
        for future in concurrent.futures.as_completed(futures):
            mall_name = futures[future]
            try:
                all_results += future.result()
            except Exception as e:
                print(f"[오류] {mall_name} 테스트 실패: {e}")

    return all_results


def cleanup_old_files(base_dir: str, days: int = 7):
    """7일 이전 파일 정리"""
    if not os.path.exists(base_dir):
        return

    cutoff = now_kst() - timedelta(days=days)
    try:
        for file in os.listdir(base_dir):
            file_path = os.path.join(base_dir, file)
            if os.path.isfile(file_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path), KST)
                if mtime < cutoff:
                    os.remove(file_path)
                    print(f"[정리] 삭제: {file}")
    except Exception as e:
        print(f"[정리] 오류: {e}")


def main():
    headless = "--show" not in sys.argv
    start = time.time()
    print("\n" + "=" * 60)
    print(f"드림몰 UI 테스트 시작: {now_kst().strftime('%Y-%m-%d %H:%M:%S')} (KST)")
    print("=" * 60)
    print("\n콘솔 출력을 통해 상세한 테스트 과정을 추적할 수 있습니다.")
    print("   팝업, 검색, 카테고리 등 각 테스트의 성공/실패 원인이 표시됩니다.\n")

    # 7일 이전 스크린샷, 보고서, 비디오 정리
    base_dir = os.path.dirname(__file__)
    print("\n[정리 중] 이전 파일 정리...")
    cleanup_old_files(os.path.join(base_dir, "screenshots"))
    cleanup_old_files(os.path.join(base_dir, "reports"))
    cleanup_old_files(os.path.join(base_dir, "videos"))

    cfg = load_config()
    results = run_all(cfg, headless=headless)
    elapsed = time.time() - start

    # 결과 요약
    fail_count = sum(1 for r in results if not r.passed)
    pass_count = len(results) - fail_count

    print("\n" + "=" * 60)
    print(f"테스트 완료 | 통과: {pass_count}/{len(results)} | 실패: {fail_count}/{len(results)}")
    print(f"소요 시간: {elapsed:.1f}초")
    print("=" * 60)

    report = build_report(results, elapsed)
    print("\n" + report)

    # MD 파일로 저장
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    ts = now_kst().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(reports_dir, f"report_{ts}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n리포트 저장: {report_path}")

    # 두레이 발송 (간단한 요약 메시지)
    # webhook_url = os.environ.get("DOORAY_WEBHOOK_URL", "")
    # bot_name = cfg["dooray"]["bot_name"]
    # if webhook_url:
    #     simple_msg = build_simple_message(results)
    #     ok = dooray_send(webhook_url, bot_name, simple_msg)
    #     print(f"두레이 발송: {'성공 ✓' if ok else '실패 ✗'}")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
