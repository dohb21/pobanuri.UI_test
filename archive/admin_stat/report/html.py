from datetime import datetime


def build_html_report(headers, rows, top5, top10, chart_paths=None) -> str:
    """HTML 형식의 리포트 — PDF 1페이지 최적화"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S (KST)")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>드림몰 현황 리포트</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Malgun Gothic', -apple-system, BlinkMacSystemFont, sans-serif;
            max-width: 980px;
            margin: 0 auto;
            padding: 14px;
            background: #f5f5f5;
            font-size: 12px;
            color: #333;
        }}
        h1 {{
            font-size: 16px;
            border-bottom: 3px solid #007bff;
            padding-bottom: 5px;
            color: #007bff;
            margin-bottom: 7px;
        }}
        h2 {{
            font-size: 12px;
            border-left: 4px solid #007bff;
            padding-left: 7px;
            margin: 10px 0 5px;
            font-weight: bold;
        }}
        h3 {{
            font-size: 11px;
            color: #555;
            margin-bottom: 3px;
        }}
        .meta {{
            background: #e7f3ff;
            padding: 4px 10px;
            border-radius: 4px;
            margin-bottom: 9px;
            font-size: 11px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            margin-bottom: 10px;
        }}
        th {{
            background: #004085;
            color: white;
            padding: 5px 5px;
            text-align: center;
            font-size: 10.5px;
            white-space: nowrap;
        }}
        td {{
            padding: 4px 5px;
            border-bottom: 1px solid #eee;
            text-align: center;
            font-size: 10.5px;
        }}
        tr:last-child td {{ border-bottom: none; }}
        .two-col {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }}
        .two-col > div {{
            flex: 1;
            background: white;
            padding: 8px 10px;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }}
        .two-col ol {{
            margin: 4px 0 0;
            padding-left: 16px;
        }}
        .two-col li {{
            margin: 2px 0;
            line-height: 1.5;
            font-size: 11px;
        }}
        .chart-item {{
            background: white;
            padding: 6px 8px;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            margin-bottom: 8px;
        }}
        .chart-item img {{
            max-width: 100%;
            display: block;
        }}
        .empty {{ color: #999; font-style: italic; font-size: 11px; }}
        @media print {{
            body {{ background: white; padding: 0; }}
        }}
    </style>
</head>
<body>
    <h1>드림몰 현황 리포트</h1>
    <div class="meta"><strong>실행:</strong> {now}</div>

    <h2>로그인/신규회원 Summary (최근 3일)</h2>
"""

    # 테이블
    if headers and rows:
        html += "    <table>\n        <thead><tr>\n"
        for header in headers:
            html += f"            <th>{header}</th>\n"
        html += "        </tr></thead>\n        <tbody>\n"
        for row in rows:
            html += "        <tr>\n"
            for cell in row:
                html += f"            <td>{cell}</td>\n"
            html += "        </tr>\n"
        html += "        </tbody>\n    </table>\n"
    else:
        html += '    <p class="empty">데이터 없음</p>\n'

    # TOP 5 + TOP 10 (좌우 2분할)
    html += '    <div class="two-col">\n'

    html += '        <div>\n            <h2>TOP 5 상품 (최근 1주)</h2>\n'
    if top5:
        html += "            <ol>\n"
        for _, name in top5:
            html += f"                <li>{name}</li>\n"
        html += "            </ol>\n"
    else:
        html += '            <p class="empty">데이터 없음</p>\n'
    html += "        </div>\n"

    html += '        <div>\n            <h2>TOP 10 검색키워드 (최근 1주)</h2>\n'
    if top10:
        html += "            <ol>\n"
        for _, kw in top10:
            html += f"                <li>{kw}</li>\n"
        html += "            </ol>\n"
    else:
        html += '            <p class="empty">데이터 없음</p>\n'
    html += "        </div>\n"

    html += "    </div>\n"

    # 주문/클레임 차트
    html += "    <h2>주문/클레임 차트 (최근 3일)</h2>\n"
    if chart_paths and "charts" in chart_paths:
        html += f"""    <div class="chart-item">
        <img src="{chart_paths['charts']}" alt="주문/클레임 차트">
    </div>
"""
    else:
        html += '    <p class="empty">차트 데이터 없음</p>\n'

    html += "</body>\n</html>\n"
    return html
