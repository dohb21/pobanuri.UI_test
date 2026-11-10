import math
import os
from datetime import datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

_DONUT_COLORS = ["#14b8a6", "#0284c7", "#f97316", "#ef4444", "#8b5cf6", "#84cc16", "#ec4899"]


def _draw_half_donut(ax, labels, rates, title, bg_color="#f1f5f9"):
    """반원 도넛 차트 그리기. labels/rates가 비어있으면 '데이터 없음' 표시."""
    # 데이터 없는 경우 — 깔끔한 빈 상태
    if not labels or not rates or sum(rates) == 0:
        ax.axis("off")
        ax.set_title(title, fontsize=9, fontweight="bold", color="#1e293b", pad=6)
        ax.plot([0.05, 0.45], [0.5, 0.5], color="#cbd5e1",
                linewidth=1.2, transform=ax.transAxes, clip_on=False)
        ax.text(0.5, 0.42, "데이터 없음", ha="center", va="center",
                fontsize=9, color="#94a3b8", transform=ax.transAxes)
        return

    total = sum(rates)
    # dummy 슬라이스로 하단 반원 채움
    vals = list(rates) + [total]
    colors = _DONUT_COLORS[:len(labels)] + [bg_color]

    # pie() 먼저 그린 후 axis/limit 조정 (GridSpec 충돌 방지)
    wedges, _ = ax.pie(
        vals,
        colors=colors,
        startangle=180,
        counterclock=False,
        wedgeprops=dict(width=0.46, edgecolor="white", linewidth=1.5),
    )
    wedges[-1].set_alpha(0)  # dummy 슬라이스 숨김

    # 각 슬라이스 중앙에 항목명 + 비율 텍스트
    for wedge, label, rate in zip(wedges[:-1], labels, rates):
        mid_angle = (wedge.theta1 + wedge.theta2) / 2
        rad = math.radians(mid_angle)
        r = 0.71
        x, y = r * math.cos(rad), r * math.sin(rad)
        short = label[:6] + "…" if len(label) > 6 else label
        ax.text(x, y, f"{short}\n{rate:.1f}%",
                ha="center", va="center", fontsize=6.5,
                color="white", fontweight="bold",
                multialignment="center")

    # 상단 반원만 보이도록 y 범위 제한 (set_aspect는 pie()가 이미 설정)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title(title, fontsize=9, fontweight="bold", color="#1e293b", pad=6)


def _setup_korean_font() -> None:
    import matplotlib.font_manager as fm
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    for font_path in candidates:
        if os.path.exists(font_path):
            prop = fm.FontProperties(fname=font_path)
            plt.rcParams["font.family"] = prop.get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def draw_combined_a5(order_data: dict, claim_data: dict | None, fpath: str) -> bool:
    """4개 차트를 A5 세로(5.83"×8.27") 한 장 이미지로 합성"""
    try:
        _setup_korean_font()

        dates     = [d[-5:] for d in order_data["dates"][-4:-1]]
        xs        = list(range(len(dates)))
        order_amt = order_data["orderAmt"][-4:-1]
        can_amt   = order_data["canAmt"][-4:-1]
        ret_amt   = order_data["retAmt"][-4:-1]
        order_cnt = order_data["orderCnt"][-4:-1]
        can_cnt   = order_data["canCnt"][-4:-1]
        ret_cnt   = order_data["retCnt"][-4:-1]
        has_reason = claim_data is not None
        claim_cnt  = [c + r for c, r in zip(can_cnt, ret_cnt)] if has_reason else [0] * len(xs)
        n_rows     = 4 if has_reason else 3
        heights    = [3, 3, 2, 3] if has_reason else [3, 3, 2]

        fig = plt.figure(figsize=(5.83, 8.27))
        gs  = GridSpec(n_rows, 1, figure=fig, height_ratios=heights,
                       hspace=0.55, left=0.15, right=0.97, top=0.97, bottom=0.04)

        def _annotate(ax, vals, comma=False):
            for i, v in enumerate(vals):
                ax.annotate(f"{v:,}" if comma else str(v), (i, v),
                            xytext=(0, 5), textcoords="offset points",
                            ha="center", fontsize=7)

        ax0 = fig.add_subplot(gs[0])
        for vals, label, color in [
            (order_amt, "주문금액", "#4e79a7"),
            (can_amt,   "취소금액", "#f28e2b"),
            (ret_amt,   "반품금액", "#e15759"),
        ]:
            ax0.plot(xs, vals, marker="o", markersize=4, label=label, color=color)
            _annotate(ax0, vals, comma=True)
        ax0.set_xticks(xs); ax0.set_xticklabels(dates, fontsize=7)
        ax0.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
        ax0.tick_params(axis="y", labelsize=7)
        ax0.set_title("주문/취소/반품 금액 (최근 3일)", fontsize=9, pad=3)
        ax0.legend(fontsize=7, loc="upper left")

        ax1 = fig.add_subplot(gs[1])
        for vals, label, color in [
            (order_cnt, "주문건수", "#4e79a7"),
            (can_cnt,   "취소건수", "#f28e2b"),
            (ret_cnt,   "반품건수", "#e15759"),
        ]:
            ax1.plot(xs, vals, marker="o", markersize=4, label=label, color=color)
            _annotate(ax1, vals)
        ax1.set_xticks(xs); ax1.set_xticklabels(dates, fontsize=7)
        ax1.tick_params(axis="y", labelsize=7)
        ax1.set_title("주문/취소/반품 건수 (최근 3일)", fontsize=9, pad=3)
        ax1.legend(fontsize=7, loc="upper left")

        ax2 = fig.add_subplot(gs[2])
        bars = ax2.bar(xs, claim_cnt, color="#76b7b2", label="클레임(취소+반품)")
        ax2.bar_label(bars, padding=2, fontsize=8)
        ax2.set_xticks(xs); ax2.set_xticklabels(dates, fontsize=7)
        ax2.tick_params(axis="y", labelsize=7)
        ax2.set_title("클레임 건수 (최근 3일)", fontsize=9, pad=3)
        ax2.legend(fontsize=7)

        if has_reason:
            ax3 = fig.add_subplot(gs[3])
            _draw_half_donut(ax3, claim_data["labels"], claim_data["rates"], "클레임 사유 TOP5")

        fig.savefig(fpath, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    except Exception:
        return False


def draw_report_image(
    headers: list, rows: list,
    top5: list, top10: list,
    order_data: dict | None, claim_data: dict | None,
    fpath: str,
) -> bool:
    """개선된 3×2 그리드 카카오톡 전송용 이미지 생성 함수"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
        from matplotlib.gridspec import GridSpec
        _setup_korean_font()

        has_order  = order_data is not None
        has_reason = claim_data is not None

        # 1. 전체 캔버스 설정 (크기를 살짝 늘려 여백 확보)
        fig = plt.figure(figsize=(8.0, 10.5))
        fig.patch.set_facecolor("#f1f5f9")

        gs = GridSpec(4, 1, figure=fig,
                      height_ratios=[0.3, 1.8, 1.7, 1.7],
                      hspace=0.55,
                      left=0.07, right=0.93, top=0.95, bottom=0.05)
        gs_r1 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[1], width_ratios=[6, 4], wspace=0.08)
        gs_r2 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[2], wspace=0.25)
        gs_r3 = GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[3], wspace=0.25)

        # ── 세련된 모던 컬러 팔레트 정의 ──────────────────────────────
        C_PRIMARY = "#1e293b"  # 딥 네이비 (메인 타이틀/헤더)
        C_TEXT_MAIN = "#334155"
        C_BORDER = "#cbd5e1"
        C_TH_BG = "#334155"    # 테이블 헤더 배경
        C_ROW_ALT = "#f8fafc"  # 지브라 패턴 연한 배경
        
        # 차트 선 색상 (토마토/오렌지/스카이블루 계열로 트렌디하게)
        C_ORDER = "#0284c7"    # 주문 (블루)
        C_CANCEL = "#f97316"   # 취소 (오렌지)
        C_RETURN = "#ef4444"   # 반품 (레드)
        C_CLAIM = "#14b8a6"    # 클레임 (민트/티일)

        # ── 제목 영역 ─────────────────────────────────────────
        ax_title = fig.add_subplot(gs[0])
        ax_title.axis("off")
        ax_title.text(0.5, 0.5,
                      f"드림몰 Admin 통계  ({(datetime.now(_KST) - timedelta(days=1)).strftime('%Y.%m.%d')})",
                      ha="center", va="center",
                      fontsize=14, fontweight="bold", color=C_PRIMARY,
                      transform=ax_title.transAxes)

        # ── 테이블 스타일 공통 헬퍼 (패딩 및 폰트 개선) ──────────────────
        def _apply_table_style(tbl, fontsize=8):
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(fontsize)
            # 테이블 셀 높이(패딩) 넓히기
            for position, cell in tbl.get_celld().items():
                cell.set_height(0.18)  # 셀 높이 가독성 확보
            
            for (r, _), cell in tbl.get_celld().items():
                if r == 0:
                    cell.set_facecolor(C_TH_BG)
                    cell.set_text_props(color="white", fontweight="bold", ha="center")
                elif r % 2 == 1:
                    cell.set_facecolor(C_ROW_ALT)
                    cell.set_text_props(color=C_TEXT_MAIN)
                else:
                    cell.set_facecolor("#ffffff")
                    cell.set_text_props(color=C_TEXT_MAIN)
                cell.set_edgecolor(C_BORDER)
                cell.set_linewidth(0.6)

        # ── Row 1 Left: TOP5 상품 ─────────────────────────────────────
        ax_top5 = fig.add_subplot(gs_r1[0])
        ax_top5.axis("off")
        if top5:
            cell_data = [
                [str(i + 1), nm]
                for i, (_, nm) in enumerate(top5[:5])
            ]
            tbl5 = ax_top5.table(
                cellText=cell_data, colLabels=["#", "TOP5 상품"],
                cellLoc="left", bbox=[0, 0, 1, 1], colWidths=[0.08, 0.92],
            )
            _apply_table_style(tbl5)
            for (_, c), cell in tbl5.get_celld().items():
                if c == 0:
                    cell.get_text().set_ha("center")
                elif c == 1:
                    cell.PAD = 0.02
        else:
            ax_top5.text(0.5, 0.5, "데이터 없음", ha="center", va="center", fontsize=8, transform=ax_top5.transAxes)

        # ── Row 1 Right: TOP10 검색어 (중앙 가이드선 제거, 여백 확보) ──────
        ax_kw = fig.add_subplot(gs_r1[1])
        ax_kw.axis("off")
        if top10:
            kw_data = []
            for i in range(5):
                l_kw = top10[i][1][:10] + ("…" if len(top10[i][1]) > 10 else "") if i < len(top10) else ""
                r_kw = top10[i + 5][1][:10] + ("…" if len(top10[i + 5][1]) > 10 else "") if i + 5 < len(top10) else ""
                kw_data.append([str(i + 1), l_kw, str(i + 6), r_kw])
            tbl_kw = ax_kw.table(
                cellText=kw_data,
                colLabels=["#", "검색어", "#", "검색어"],
                cellLoc="left", bbox=[0, 0, 1, 1],
                colWidths=[0.10, 0.40, 0.10, 0.40],
            )
            _apply_table_style(tbl_kw)
            for (_, c), cell in tbl_kw.get_celld().items():
                if c in (0, 2):
                    cell.get_text().set_ha("center")
        else:
            ax_kw.text(0.5, 0.5, "데이터 없음", ha="center", va="center", fontsize=8, transform=ax_kw.transAxes)

        # ── Row 2 Left: 로그인/신규가입 요약 ──────────────────────────
        ax_summary = fig.add_subplot(gs_r2[0])
        ax_summary.axis("off")
        ax_summary.set_title("로그인 / 신규가입", fontsize=10, fontweight="bold", color=C_PRIMARY, pad=10)
        if rows and headers:
            clean_rows = []
            for r in rows:
                clean_rows.append([str(cell).replace("-1387", "0") if "1387" in str(cell) else str(cell) for cell in r])
            tbl_s = ax_summary.table(
                cellText=clean_rows, colLabels=headers,
                cellLoc="center", loc="center",
                colWidths=[0.24, 0.19, 0.19, 0.19, 0.19],
            )
            _apply_table_style(tbl_s, fontsize=7.5)

        # ── 차트 공통 스타일 적용 헬퍼 ──────────────────────────────────
        def _clean_chart_spine(ax, title, max_val=0, is_all_zero=False):
            ax.set_title(title, fontsize=10, fontweight="bold", color=C_PRIMARY, pad=10)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color(C_BORDER)
            ax.spines["bottom"].set_color(C_BORDER)
            ax.grid(axis="y", linestyle="--", alpha=0.5, color=C_BORDER)
            ax.set_facecolor("#ffffff")
            if is_all_zero:
                ax.set_ylim(0, 5)
            elif max_val > 0:
                ax.set_ylim(bottom=0, top=max_val * 1.25)
            else:
                ax.set_ylim(bottom=0)

        if has_order:
            dates     = [d[-5:] for d in order_data["dates"][-4:-1]]
            xs        = list(range(len(dates)))
            order_amt = order_data["orderAmt"][-4:-1]
            can_amt   = order_data["canAmt"][-4:-1]
            ret_amt   = order_data["retAmt"][-4:-1]
            order_cnt  = order_data["orderCnt"][-4:-1]
            can_cnt    = order_data["canCnt"][-4:-1]
            ret_cnt    = order_data["retCnt"][-4:-1]
            claim_cnt  = [c + r for c, r in zip(can_cnt, ret_cnt)] if has_reason else [0] * len(xs)

            def _ann(ax, vals, comma=False, offset=7):
                for i, v in enumerate(vals):
                    # 값이 0일 때 선과 겹치면 패딩 조정
                    text_offset = offset if v > 0 else 6
                    ax.annotate(f"{v:,}" if comma else str(v), (i, v),
                                xytext=(0, text_offset), textcoords="offset points",
                                ha="center", fontsize=8, color=C_TEXT_MAIN,
                                fontweight="bold" if v > 0 else "normal")

            # Row 2 Right: 주문/취소/반품 금액
            ax_amt = fig.add_subplot(gs_r2[1])
            ax_amt.plot(xs, order_amt, marker="o", markersize=5, linewidth=2, label="주문", color=C_ORDER)
            ax_amt.plot(xs, can_amt, marker="o", markersize=5, linewidth=1.5, label="취소", color=C_CANCEL)
            ax_amt.plot(xs, ret_amt, marker="o", markersize=5, linewidth=1.5, label="반품", color=C_RETURN)
            
            _ann(ax_amt, order_amt, comma=True)
            _ann(ax_amt, can_amt, comma=True)
            _ann(ax_amt, ret_amt, comma=True)
            
            ax_amt.set_xticks(xs)
            ax_amt.set_xticklabels(dates, fontsize=8)
            ax_amt.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
            ax_amt.tick_params(axis="both", colors=C_TEXT_MAIN, labelsize=8)
            ax_amt.set_xmargin(0.15)
            max_amt = max(max(order_amt), max(can_amt), max(ret_amt))
            _clean_chart_spine(ax_amt, "주문/취소/반품 금액 (최근 3일)", max_val=max_amt)
            ax_amt.legend(fontsize=7.5, loc="upper left", frameon=True, facecolor="#ffffff", edgecolor=C_BORDER)

            # Row 3 Right: 주문/취소/반품 건수
            ax_cnt = fig.add_subplot(gs_r3[1])
            ax_cnt.plot(xs, order_cnt, marker="o", markersize=5, linewidth=2, label="주문", color=C_ORDER)
            ax_cnt.plot(xs, can_cnt, marker="o", markersize=5, linewidth=1.5, label="취소", color=C_CANCEL)
            ax_cnt.plot(xs, ret_cnt, marker="o", markersize=5, linewidth=1.5, label="반품", color=C_RETURN)
            
            _ann(ax_cnt, order_cnt)
            _ann(ax_cnt, can_cnt)
            _ann(ax_cnt, ret_cnt)
            
            ax_cnt.set_xticks(xs)
            ax_cnt.set_xticklabels(dates, fontsize=8)
            ax_cnt.tick_params(axis="both", colors=C_TEXT_MAIN, labelsize=8)
            ax_cnt.set_xmargin(0.15)
            max_cnt = max(max(order_cnt), max(can_cnt), max(ret_cnt))
            _clean_chart_spine(ax_cnt, "주문/취소/반품 건수 (최근 3일)", max_val=max_cnt)
            ax_cnt.legend(fontsize=7.5, loc="upper left", frameon=True, facecolor="#ffffff", edgecolor=C_BORDER)

            # Row 3 Left: 클레임 사유 반원 도넛 차트
            ax_claim = fig.add_subplot(gs_r3[0])
            if has_reason:
                _draw_half_donut(ax_claim, claim_data["labels"], claim_data["rates"],
                                 "클레임 사유 TOP5", bg_color="#f1f5f9")
            else:
                ax_claim.axis("off")
                ax_claim.set_title("클레임 사유 TOP5", fontsize=10, fontweight="bold",
                                   color=C_PRIMARY, pad=10)
                ax_claim.plot([0.05, 0.45], [0.5, 0.5], color=C_BORDER,
                              linewidth=1.2, transform=ax_claim.transAxes, clip_on=False)
                ax_claim.text(0.5, 0.45, "데이터 없음", ha="center", va="center",
                              fontsize=9, color="#94a3b8", transform=ax_claim.transAxes)

        # 저장 포맷 최적화 (배경색 투명화 방지 및 선명도 확보)
        fig.savefig(fpath, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return True
    except Exception as e:
        print(f"[카카오 이미지 개선본 생성 실패] {e}")
        return False
