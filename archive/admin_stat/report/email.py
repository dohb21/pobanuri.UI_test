import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))

# chart_paths_abs 의 key → CID 매핑
_CID = {
    "charts": "chart_combined",
    "report": "report_image",
}
_CHART_LABEL = {
    "charts": "주문/클레임 차트",
}


def build_email_html(
    headers: list, rows: list, top5: list, top10: list, chart_keys: list = None
) -> str:
    today = (datetime.now(_KST) - timedelta(days=1)).strftime("%Y년 %m월 %d일")
    chart_keys = chart_keys or []

    th_cells = "".join(f"<th>{h}</th>" for h in headers)
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )

    top5_rows = "".join(
        f"<tr><td>{r}</td><td>{n}</td></tr>" for r, n in top5
    ) or "<tr><td colspan='2'>데이터 없음</td></tr>"

    top10_rows = "".join(
        f"<tr><td>{r}</td><td>{k}</td></tr>" for r, k in top10
    ) or "<tr><td colspan='2'>데이터 없음</td></tr>"

    chart_html = ""
    for key in chart_keys:
        cid = _CID.get(key, key)
        label = _CHART_LABEL.get(key, key)
        chart_html += f"""
        <div class="chart-block">
          <h3 class="chart-title">{label} 추이</h3>
          <img src="cid:{cid}" alt="{label}" style="max-width:100%;border-radius:6px;">
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
  body{{font-family:'Malgun Gothic',sans-serif;font-size:13px;color:#333;background:#f5f5f5;margin:0;padding:20px}}
  .wrap{{max-width:920px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
  .hd{{background:#1a73e8;color:#fff;padding:20px 28px}}
  .hd h1{{margin:0;font-size:20px}} .hd p{{margin:4px 0 0;font-size:12px;opacity:.85}}
  .sec{{padding:20px 28px;border-bottom:1px solid #eee}}
  h2{{font-size:15px;color:#1a73e8;margin:0 0 12px}} h3.chart-title{{font-size:13px;color:#555;margin:0 0 8px}}
  .tbl-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{background:#1a73e8;color:#fff;padding:7px 8px;text-align:center;white-space:nowrap}}
  td{{padding:6px 8px;border-bottom:1px solid #eee;text-align:center}}
  tr:nth-child(even) td{{background:#f9f9f9}}
  .two-col{{display:flex;gap:20px}} .two-col>div:first-child{{flex:2}} .two-col>div:last-child{{flex:1}}
  .chart-block{{margin-bottom:20px}}
  .ft{{padding:14px 28px;font-size:11px;color:#999;text-align:center}}
  @media (max-width:600px){{
    body{{padding:0}}
    .wrap{{border-radius:0;box-shadow:none}}
    .sec{{padding:16px}}
    .two-col{{flex-direction:column}}
    .two-col>div:first-child,.two-col>div:last-child{{flex:unset}}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hd"><h1>드림몰 Admin 통계 리포트</h1><p>{today} 기준</p></div>

  <div class="sec">
    <h2>로그인 / 신규 회원</h2>
    <p style="margin:0 0 10px;font-size:11px;color:#999">※ 내용이 잘린 경우 표를 좌우로 스크롤하여 확인하세요.</p>
    <div class="tbl-wrap"><table><thead><tr>{th_cells}</tr></thead><tbody>{table_rows}</tbody></table></div>
  </div>

  {"<div class='sec'><h2>차트</h2>" + chart_html + "</div>" if chart_html else ""}

  <div class="sec">
    <div class="two-col">
      <div>
        <h2>TOP 5 상품</h2>
        <table><thead><tr><th>순위</th><th>상품명</th></tr></thead><tbody>{top5_rows}</tbody></table>
      </div>
      <div>
        <h2>TOP 10 검색 키워드</h2>
        <table><thead><tr><th>순위</th><th>키워드</th></tr></thead><tbody>{top10_rows}</tbody></table>
      </div>
    </div>
  </div>

  <div class="ft">자동 발송 메일입니다 · 드림몰 Admin 통계봇</div>
</div>
</body>
</html>"""


def build_report_image_html() -> str:
    today = (datetime.now(_KST) - timedelta(days=1)).strftime("%Y년 %m월 %d일")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
  body{{font-family:'Malgun Gothic',sans-serif;margin:0;padding:20px;background:#f1f5f9}}
  .wrap{{max-width:680px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)}}
  .hd{{background:#1e293b;color:#fff;padding:16px 24px}}
  .hd h1{{margin:0;font-size:18px}} .hd p{{margin:4px 0 0;font-size:11px;opacity:.8}}
  .body{{padding:20px 24px;text-align:center}}
  .ft{{padding:12px 24px;font-size:11px;color:#999;text-align:center}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hd"><h1>드림몰 Admin 통계 리포트</h1><p>{today} 기준</p></div>
  <div class="body">
    <img src="cid:report_image" alt="드림몰 통계 리포트" style="max-width:100%;border-radius:4px;">
  </div>
  <div class="ft">자동 발송 메일입니다 · 드림몰 Admin 통계봇</div>
</div>
</body>
</html>"""


def send_email(
    subject: str,
    html_body: str,
    to_addrs: list[str],
    chart_paths: dict = None,
) -> bool:
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    from_addr = os.getenv("EMAIL_FROM", "")
    password = os.getenv("EMAIL_PASSWORD", "")

    if not from_addr or not password:
        print("⚠️ 이메일 설정 없음 (.env에 EMAIL_FROM, EMAIL_PASSWORD 필요)")
        return False
    if not to_addrs:
        print("⚠️ 수신자 없음 (.env에 EMAIL_TO 필요)")
        return False

    # multipart/related: HTML + 인라인 이미지
    related = MIMEMultipart("related")
    related.attach(MIMEText(html_body, "html", "utf-8"))

    for key, path in (chart_paths or {}).items():
        if not os.path.exists(path):
            continue
        cid = _CID.get(key, key)
        with open(path, "rb") as f:
            img = MIMEImage(f.read())
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
        related.attach(img)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.attach(related)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, to_addrs, msg.as_bytes())
        return True
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
        return False
