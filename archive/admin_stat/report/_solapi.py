import hashlib
import hmac
import uuid
from datetime import datetime, timezone


def solapi_auth_header(api_key: str, api_secret: str) -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    salt = str(uuid.uuid4()).replace("-", "")
    data = date + salt
    signature = hmac.new(
        api_secret.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}"
