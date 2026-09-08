from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from Models.Model_Link import Model_Link
from Utils.common import hash_password

LINK_FIELDS = "id, user_id, link_name, link_description, destination_link, slug, visits, max_age_minutes, created_at, updated_at, status"
RAW_FIELDS = LINK_FIELDS + ", access_code_hash"


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace(" ", "T").replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def public_link(link: dict[str, Any] | None) -> dict[str, Any] | None:
    if not link:
        return None
    result = {key: value for key, value in link.items() if key not in {"access_code_hash", "user_id"}}
    result["is_secured"] = bool(link.get("access_code_hash"))
    return result


async def get_raw_link(link_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    where = {"id": link_id}
    if user_id is not None:
        where["user_id"] = user_id
    rows = await Model_Link.select(columns=RAW_FIELDS, where=where, limit=1)
    return rows[0] if rows else None


async def get_link(link_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    return public_link(await get_raw_link(link_id, user_id))


async def get_link_by_slug(slug: str) -> dict[str, Any] | None:
    rows = await Model_Link.select(columns=RAW_FIELDS, where={"slug": slug}, limit=1)
    return rows[0] if rows else None


async def expire_link(link_id: int) -> None:
    link = await get_raw_link(link_id)
    if not link or link["status"] == "deleted" or link["max_age_minutes"] is None:
        return
    expired = (datetime.now(timezone.utc) - parse_time(link["created_at"])).total_seconds() >= link["max_age_minutes"] * 60
    next_status = "expired" if expired else "active"
    if link["status"] != next_status:
        await Model_Link.update({"status": next_status, "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}, {"id": link_id})


async def cleanup_deleted_links(user_id: int) -> None:
    rows = await Model_Link.select(columns="id, status, updated_at", where={"user_id": user_id})
    cutoff = datetime.now(timezone.utc).timestamp() - 5 * 86400
    for row in rows:
        if parse_time(row["updated_at"]).timestamp() <= cutoff:
            if row["status"] == "expired":
                await Model_Link.update({"status": "deleted", "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}, {"id": row["id"]})
            elif row["status"] == "deleted":
                await Model_Link.delete({"id": row["id"]})


async def list_links(user_id: int, include_deleted: bool = True) -> list[dict[str, Any]]:
    await cleanup_deleted_links(user_id)
    rows = await Model_Link.select(columns=RAW_FIELDS, where={"user_id": user_id})
    for row in rows:
        await expire_link(row["id"])
    rows = await Model_Link.select(columns=RAW_FIELDS, where={"user_id": user_id})
    if not include_deleted:
        rows = [row for row in rows if row["status"] != "deleted"]
    return [public_link(row) for row in rows]  # type: ignore[misc]


async def create_link(user_id: int, values: dict[str, Any]) -> dict[str, Any]:
    values = dict(values)
    values.pop("security_action", None)
    access_code = values.pop("access_code", None)
    values["user_id"] = user_id
    values["access_code_hash"] = hash_password(access_code) if access_code else None
    values["slug"] = values.get("slug") or f"pending-{datetime.now(timezone.utc).timestamp()}"
    row = await Model_Link.insert(values)
    return public_link(await get_raw_link(int(row["id"])))  # type: ignore[return-value]


async def update_link(link_id: int, user_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
    values = dict(values)
    action = values.pop("security_action", "keep")
    access_code = values.pop("access_code", None)
    if action == "remove":
        values["access_code_hash"] = None
    elif action == "update":
        values["access_code_hash"] = hash_password(access_code) if access_code else None
    values["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await Model_Link.update(values, {"id": link_id, "user_id": user_id})
    await expire_link(link_id)
    return await get_link(link_id, user_id)


async def restore_link(link_id: int, user_id: int) -> dict[str, Any] | None:
    link = await get_raw_link(link_id, user_id)
    if not link or link["status"] != "deleted":
        return None
    expires = None if link["max_age_minutes"] is None else parse_time(link["created_at"]).timestamp() + link["max_age_minutes"] * 60
    status = "active" if expires is None or expires > datetime.now(timezone.utc).timestamp() else "expired"
    await Model_Link.update({"status": status, "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}, {"id": link_id, "user_id": user_id})
    return await get_link(link_id, user_id)


async def dashboard_stats(user_id: int) -> dict[str, Any]:
    links = await list_links(user_id, include_deleted=True)
    active = [link for link in links if link["status"] == "active"]
    expired = [link for link in links if link["status"] == "expired"]
    deleted = [link for link in links if link["status"] == "deleted"]
    now = datetime.now(timezone.utc)

    def minutes_left(link: dict[str, Any]) -> float | None:
        if link["max_age_minutes"] is None:
            return None
        return (parse_time(link["created_at"]).timestamp() + link["max_age_minutes"] * 60 - now.timestamp()) / 60

    near_expiry = sorted(
        [link for link in active if (minutes := minutes_left(link)) is not None and 0 < minutes < 5],
        key=lambda link: minutes_left(link) or 0,
    )[:3]
    return {
        "total_links": len(active),
        "total_visits": sum(link["visits"] for link in active),
        "expired_links": len(expired),
        "deleted_links": len(deleted),
        "recent_links": sorted(links, key=lambda link: link["updated_at"], reverse=True)[:5],
        "near_expiry_links": near_expiry,
    }
