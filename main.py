import os
import sys
import time
import random
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

from tests.base import TestResult, init_browser, run_test
from tests import test_main, test_popup, test_search, test_category, test_gnb, test_popular, test_cart, test_shipping
from report.generator import build_report, build_simple_message
from report.dooray import send as dooray_send


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_platform(playwright, cfg: dict, mobile: bool) -> list[TestResult]:
    platform = "Mobile" if mobile else "PC"
    url = cfg["urls"]["mobile"] if mobile else cfg["urls"]["pc"]
    username = cfg["account"]["username"]
    password = cfg["account"]["password"]
    valid_kws = cfg["search"]["valid"]
    invalid_kws = cfg["search"]["invalid"]
    cat_pool = cfg["categories"]["pool"]
    cat_count = cfg["categories"]["count"]

    results = []
    browser, context, page = init_browser(playwright, mobile=mobile)

    try:
        # 1. 메인 화면 진입
        print(f"  [1/8] 메인 화면 진입...", end=" ", flush=True)
        result = run_test("메인 화면 진입", platform, page,
                         lambda p: test_main.run(p, url))
        results.append(result)
        print("✅" if result.passed else f"❌ {result.error_msg[:30]}")

        # 2. 메인 팝업 (비디오 녹화 + 스크린샷)
        print(f"  [2/8] 메인 팝업 노출...", end=" ", flush=True)
        browser2, ctx2, page2 = init_browser(playwright, mobile=mobile, record_video=True)
        try:
            result = run_test("메인 팝업 노출", platform, page2,
                            lambda p: test_popup.run(p, url), save_all_screenshots=True)
            results.append(result)
            print("✅" if result.passed else f"❌ {result.error_msg[:30]}")
        finally:
            browser2.close()

        # 3. 검색
        print(f"  [3/8] 검색 기능...", end=" ", flush=True)
        result = run_test("검색 기능", platform, page,
                         lambda p: test_search.run(p, url, valid_kws, invalid_kws))
        results.append(result)
        print("✅" if result.passed else f"❌ {result.error_msg[:30]}")

        # 4. 카테고리
        print(f"  [4/8] 카테고리 상품 노출...", end=" ", flush=True)
        result = run_test("카테고리 상품 노출", platform, page,
                         lambda p: test_category.run(p, url, cat_pool, cat_count, mobile))
        results.append(result)
        print("✅" if result.passed else f"❌ {result.error_msg[:30]}")

        # 5. GNB 메뉴
        print(f"  [5/8] GNB 메뉴 진입...", end=" ", flush=True)
        result = run_test("GNB 메뉴 진입", platform, page,
                         lambda p: test_gnb.run(p, url))
        results.append(result)
        print("✅" if result.passed else f"❌ {result.error_msg[:30]}")

        # 6. 인기상품
        print(f"  [6/8] 하단 인기상품 목록...", end=" ", flush=True)
        result = run_test("하단 인기상품 목록", platform, page,
                         lambda p: test_popular.run(p, url))
        results.append(result)
        print("✅" if result.passed else f"❌ {result.error_msg[:30]}")

        # 7. 장바구니 (계정이 있을 때만)
        if username:
            print(f"  [7/8] 장바구니 담기...", end=" ", flush=True)
            result = run_test("장바구니 담기", platform, page,
                            lambda p: test_cart.run(p, url, username, password))
            results.append(result)
            print("✅" if result.passed else f"❌ {result.error_msg[:30]}")
        else:
            print(f"  [7/8] 장바구니 담기... ⊘ (계정 없음)")

        # 8. 배송지 등록 (계정이 있을 때만)
        if username:
            print(f"  [8/8] 배송지 등록 양식...", end=" ", flush=True)
            result = run_test("배송지 등록 양식", platform, page,
                            lambda p: test_shipping.run(p, url, username, password))
            results.append(result)
            print("✅" if result.passed else f"❌ {result.error_msg[:30]}")
        else:
            print(f"  [8/8] 배송지 등록 양식... ⊘ (계정 없음)")

    finally:
        browser.close()

    return results


def run_all(cfg: dict) -> list[TestResult]:
    all_results = []
    with sync_playwright() as playwright:
        print("\n[PC] 테스트 시작...")
        print("-" * 50)
        pc_results = run_platform(playwright, cfg, mobile=False)
        all_results += pc_results
        pc_pass = sum(1 for r in pc_results if r.passed)
        print(f"PC 완료: {pc_pass}/{len(pc_results)} 통과\n")

        print("[Mobile] 테스트 시작...")
        print("-" * 50)
        mob_results = run_platform(playwright, cfg, mobile=True)
        all_results += mob_results
        mob_pass = sum(1 for r in mob_results if r.passed)
        print(f"Mobile 완료: {mob_pass}/{len(mob_results)} 통과\n")

    return all_results


def cleanup_old_files(base_dir: str, days: int = 7):
    """7일 이전 파일 정리"""
    if not os.path.exists(base_dir):
        return

    cutoff = datetime.now() - timedelta(days=days)
    try:
        for file in os.listdir(base_dir):
            file_path = os.path.join(base_dir, file)
            if os.path.isfile(file_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < cutoff:
                    os.remove(file_path)
                    print(f"[정리] 삭제: {file}")
    except Exception as e:
        print(f"[정리] 오류: {e}")


def main():
    start = time.time()
    print("\n" + "=" * 60)
    print(f"🚀 드림몰 UI 테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\n📋 콘솔 출력을 통해 상세한 테스트 과정을 추적할 수 있습니다.")
    print("   팝업, 검색, 카테고리 등 각 테스트의 성공/실패 원인이 표시됩니다.\n")

    # 7일 이전 스크린샷, 보고서, 비디오 정리
    base_dir = os.path.dirname(__file__)
    print("\n[정리 중] 이전 파일 정리...")
    cleanup_old_files(os.path.join(base_dir, "screenshots"))
    cleanup_old_files(os.path.join(base_dir, "reports"))
    cleanup_old_files(os.path.join(base_dir, "videos"))

    cfg = load_config()
    results = run_all(cfg)
    elapsed = time.time() - start

    # 결과 요약
    fail_count = sum(1 for r in results if not r.passed)
    pass_count = len(results) - fail_count

    print("\n" + "=" * 60)
    print(f"✅ 테스트 완료 | 통과: {pass_count}/{len(results)} | 실패: {fail_count}/{len(results)}")
    print(f"⏱️  소요 시간: {elapsed:.1f}초")
    print("=" * 60)

    report = build_report(results, elapsed)
    print("\n" + report)

    # MD 파일로 저장
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(reports_dir, f"report_{ts}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 리포트 저장: {report_path}")

    # 두레이 발송 (간단한 요약 메시지)
    # webhook_url = cfg["dooray"]["webhook_url"]
    # bot_name = cfg["dooray"]["bot_name"]
    # if webhook_url:
    #     simple_msg = build_simple_message(results)
    #     ok = dooray_send(webhook_url, bot_name, simple_msg)
    #     print(f"💬 두레이 발송: {'성공 ✓' if ok else '실패 ✗'}")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
