from datetime import datetime, timedelta
from typing import List
from tests.base import TestResult


def build_report(results: List[TestResult], elapsed: float) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pc_results = [r for r in results if r.platform == "PC"]
    mob_results = [r for r in results if r.platform == "Mobile"]

    pc_pass = sum(1 for r in pc_results if r.passed)
    pc_fail = len(pc_results) - pc_pass
    mob_pass = sum(1 for r in mob_results if r.passed)
    mob_fail = len(mob_results) - mob_pass
    total_fail = pc_fail + mob_fail

    status_icon = "✅ 모두 통과" if total_fail == 0 else f"❌ {total_fail}건 실패"

    lines = [
        "# 드림몰 UI 자동 테스트 결과",
        "",
        f"**실행**: {now} | **소요**: {elapsed:.1f}초 | **결과**: {status_icon}",
        "",
        "---",
        "",
        "## 요약",
        "",
        "|  | PC | Mobile |",
        "|--|----|----|",
        f"| ✅ 통과 | {pc_pass} | {mob_pass} |",
        f"| ❌ 실패 | {pc_fail} | {mob_fail} |",
        "",
        "---",
    ]

    for platform, group in [("PC", pc_results), ("Mobile", mob_results)]:
        lines += ["", f"## [{platform}] 결과", ""]
        lines += ["| 항목 | 결과 | 비고 |", "|------|------|------|"]
        for r in group:
            icon = "✅" if r.passed else "❌"
            note = r.note if r.passed else r.error_msg[:40] if r.error_msg else "-"
            lines.append(f"| {r.name} | {icon} | {note} |")

    # 실패 항목 상세
    failed = [r for r in results if not r.passed]
    if failed:
        lines += ["", "---", "", "## ❌ 실패 항목 상세", ""]
        for r in failed:
            lines += [
                f"### [{r.platform}] {r.name}",
                f"- **오류**: {r.error_msg}",
            ]
            if r.screenshot_path:
                lines.append(f"- **스크린샷**: `{r.screenshot_path}`")
            lines.append("")

    return "\n".join(lines)


def build_simple_message(results: List[TestResult]) -> str:
    """두레이용 간단한 요약 메시지"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_fail = sum(1 for r in results if not r.passed)

    lines = [
        f"발송시각 : {now}",
        "사이트 : 드림몰",
        f"ERROR 건수 : {total_fail}건",
    ]

    if total_fail > 0:
        lines.append("ERROR 내역")
        for r in results:
            if not r.passed:
                lines.append(f"[{r.platform}] {r.name} - {r.error_msg[:60]}")

    return "\n".join(lines)
