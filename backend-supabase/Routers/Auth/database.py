from typing import Any

from Models.Model_Session import Model_Session
from Models.Model_User import Model_User
from Utils.common import hash_password


async def find_user_by_email(email: str, include_password: bool = False) -> dict[str, Any] | None:
    columns = "id, username, email, password_hash" if include_password else "id, username, email"
    users = await Model_User.select(columns=columns, where={"email": email}, limit=1)
    return users[0] if users else None


async def find_user_by_id(user_id: int, include_password: bool = False) -> dict[str, Any] | None:
    columns = "id, username, email, password_hash" if include_password else "id, username, email"
    users = await Model_User.select(columns=columns, where={"id": user_id}, limit=1)
    return users[0] if users else None


async def user_exists(username: str, email: str) -> bool:
    return bool(await Model_User.select(columns="id", where={"email": email}, limit=1)) or bool(
        await Model_User.select(columns="id", where={"username": username}, limit=1)
    )


async def create_user(username: str, email: str, password: str) -> dict[str, Any]:
    row = await Model_User.insert({"username": username, "email": email, "password_hash": hash_password(password)})
    return {key: row[key] for key in ("id", "username", "email")}


async def create_session(user_id: int, token: str, expires_at: str) -> None:
    await Model_Session.insert({"user_id": user_id, "token": token, "expires_at": expires_at})


async def get_session(token: str) -> dict[str, Any] | None:
    sessions = await Model_Session.select(where={"token": token}, limit=1)
    return sessions[0] if sessions else None


async def delete_session(token: str) -> int:
    return await Model_Session.delete({"token": token})


async def update_profile(user_id: int, username: str, email: str) -> dict[str, Any]:
    await Model_User.update({"username": username, "email": email}, {"id": user_id})
    return (await find_user_by_id(user_id))  # type: ignore[return-value]


async def update_password(user_id: int, password: str) -> None:
    await Model_User.update({"password_hash": hash_password(password)}, {"id": user_id})
