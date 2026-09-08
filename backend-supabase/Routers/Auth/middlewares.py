from datetime import datetime, timezone
from fastapi import Header

from Routers.Auth.database import delete_session, get_session


async def current_user_id(authorization: str | None = Header(default=None)) -> int | None:
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    session = await get_session(token) if token else None
    if not session:
        return None
    expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        await delete_session(token)
        return None
    return int(session["user_id"])


def bearer_token(authorization: str | None) -> str:
    return authorization.removeprefix("Bearer ").strip() if authorization else ""
