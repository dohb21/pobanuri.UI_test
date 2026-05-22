import requests


def send(webhook_url: str, bot_name: str, report_text: str) -> bool:
    """두레이 메신저 Incoming Webhook으로 보고서를 발송한다."""
    LIMIT = 3000

    if len(report_text) <= LIMIT:
        payload = {"botName": bot_name, "text": report_text}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 200

    # 요약(헤더)과 실패 상세를 분리 발송
    parts = report_text.split("## ❌ 실패 항목 상세")
    summary = parts[0].strip()
    detail = ("## ❌ 실패 항목 상세\n" + parts[1].strip()) if len(parts) > 1 else ""

    ok = True
    for text in filter(None, [summary, detail]):
        payload = {"botName": bot_name, "text": text}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code != 200:
            ok = False

    return ok
