from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


def hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_session_token() -> str:
    return secrets.token_hex(32)


def session_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def api_response(success: bool, message: str, data: Any) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}
