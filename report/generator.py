from typing import List
from tests.base import TestResult, now_kst


def build_report(results: List[TestResult], elapsed: float) -> str:
    now = now_kst().strftime("%Y-%m-%d %H:%M:%S (KST)")
    total_fail = sum(1 for r in results if not r.passed)
    total_pass = len(results) - total_fail
    status_icon = "✅ 모두 통과" if total_fail == 0 else f"❌ {total_fail}건 실패"

    # platform 값은 "몰이름 PC" / "몰이름 Mobile" 형태
    platforms = list(dict.fromkeys(r.platform for r in results))

    lines = [
        "# 드림몰 UI 자동 테스트 결과",
        "",
        f"**실행**: {now} | **소요**: {elapsed:.1f}초 | **결과**: {status_icon}",
        "",
        "---",
        "",
        "## 요약",
        "",
        "| 몰 | PC 통과 | PC 실패 | Mobile 통과 | Mobile 실패 |",
        "|---|---|---|---|---|",
    ]

    mall_names = list(dict.fromkeys(
        r.platform.rsplit(" ", 1)[0] for r in results
    ))
    for mall in mall_names:
        pc = [r for r in results if r.platform == f"{mall} PC"]
        mob = [r for r in results if r.platform == f"{mall} Mobile"]
        pc_pass = sum(1 for r in pc if r.passed)
        mob_pass = sum(1 for r in mob if r.passed)
        lines.append(
            f"| {mall} | {pc_pass}/{len(pc)} | {len(pc)-pc_pass} | {mob_pass}/{len(mob)} | {len(mob)-mob_pass} |"
        )

    lines += ["", "---"]

    for platform in platforms:
        group = [r for r in results if r.platform == platform]
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
    now = now_kst().strftime("%Y-%m-%d %H:%M:%S (KST)")
    total_fail = sum(1 for r in results if not r.passed)

    lines = [
        f"발송시각 : {now}",
        f"ERROR 건수 : {total_fail}건",
    ]

    if total_fail > 0:
        lines.append("ERROR 내역")
        for r in results:
            if not r.passed:
                lines.append(f"[{r.platform}] {r.name} - {r.error_msg[:60]}")

    return "\n".join(lines)
