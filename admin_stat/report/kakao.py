import os
from datetime import datetime

import requests

from ._solapi import solapi_auth_header


def _upload_image(api_key: str, api_secret: str, image_path: str) -> str | None:
    """차트 이미지를 Solapi에 업로드하고 imageUrl 반환"""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://api.coolsms.co.kr/kakao/v2/images",
                headers={"Authorization": solapi_auth_header(api_key, api_secret)},
                files={"file": (os.path.basename(image_path), f, "image/png")},
                timeout=30,
            )
        resp.raise_for_status()
        url = resp.json().get("imageUrl")
        if url:
            print(f"  이미지 업로드 완료: {os.path.basename(image_path)}")
        return url
    except Exception as e:
        print(f"⚠️ 카카오톡 이미지 업로드 실패: {e}")
        return None


def build_kakao_text(headers: list, rows: list, top5: list, top10: list) -> str:
    today = datetime.now().strftime("%Y년 %m월 %d일")
    lines = [f"📊 드림몰 통계 리포트\n{today}\n"]

    for row in rows:
        if len(row) >= 10:
            lines.append(
                f"▶ {row[0]}\n"
                f"  금일: {row[7]}  |  전일대비: {row[8]}  |  당월: {row[9]}"
            )

    if top5:
        lines.append("\n[TOP 5 상품]")
        for rank, name in top5:
            lines.append(f"  {rank}. {name}")

    if top10:
        lines.append("\n[TOP 10 검색 키워드]")
        for rank, kw in top10:
            lines.append(f"  {rank}. {kw}")

    return "\n".join(lines)


def send_kakao(
    text: str,
    to_numbers: list[str],
    image_path: str | None = None,
) -> bool:
    """
    Solapi FriendTalk(친구톡)으로 카카오톡 발송.
    사전 조건: 카카오채널(플러스친구) 개설 및 Solapi 연동 완료
    """
    api_key = os.getenv("SOLAPI_API_KEY", "")
    api_secret = os.getenv("SOLAPI_API_SECRET", "")
    from_number = os.getenv("SOLAPI_FROM_NUMBER", "")
    pf_id = os.getenv("KAKAO_CHANNEL_ID", "")  # 카카오채널 ID (예: @onuri-admin)

    if not api_key or not api_secret or not pf_id:
        print("⚠️ 카카오톡 설정 없음 (.env에 SOLAPI_API_KEY, SOLAPI_API_SECRET, KAKAO_CHANNEL_ID 필요)")
        return False
    if not to_numbers:
        print("⚠️ 카카오톡 수신자 없음 (.env에 KAKAO_TO 필요)")
        return False

    kakao_options: dict = {"pfId": pf_id, "content": text}

    # 이미지 업로드 (있을 경우)
    if image_path and os.path.exists(image_path):
        image_url = _upload_image(api_key, api_secret, image_path)
        if image_url:
            kakao_options["imageUrl"] = image_url

    messages = [
        {
            "to": num.replace("-", ""),
            "from": from_number,
            "type": "FT",  # FriendTalk
            "kakaoOptions": kakao_options,
        }
        for num in to_numbers
    ]

    try:
        resp = requests.post(
            "https://api.coolsms.co.kr/messages/v4/send-many",
            headers={
                "Authorization": solapi_auth_header(api_key, api_secret),
                "Content-Type": "application/json",
            },
            json={"messages": messages},
            timeout=15,
        )
        resp.raise_for_status()
        failed = resp.json().get("failedMessageList", [])
        if failed:
            print(f"⚠️ 카카오톡 일부 실패: {len(failed)}건 → {[m.get('to') for m in failed]}")
        return True
    except Exception as e:
        print(f"❌ 카카오톡 발송 실패: {e}")
        return False
