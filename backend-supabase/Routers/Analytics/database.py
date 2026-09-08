from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from Models.Model_Link import Model_Link
from Routers.Links.database import RAW_FIELDS, cleanup_deleted_links, expire_link, parse_time, public_link


def chart_link(link: dict[str, Any], now: datetime) -> dict[str, Any]:
    item = public_link(link)
    item["expiry_minutes"] = None if link["max_age_minutes"] is None else (parse_time(link["created_at"]).timestamp() + link["max_age_minutes"] * 60 - now.timestamp()) / 60
    item["deletion_hours"] = (parse_time(link["updated_at"]).timestamp() + 5 * 86400 - now.timestamp()) / 3600
    return item


def range_snapshot(links: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    result = []
    for offset in range(days):
        day = (now - timedelta(days=days - offset - 1)).date()
        bucket = [link for link in links if parse_time(link["created_at"]).date() == day]
        result.append({
            "date": day.isoformat(), "label": day.strftime("%b %d"),
            "active_links": sum(link["status"] == "active" for link in bucket),
            "expired_links": sum(link["status"] == "expired" for link in bucket),
            "deleted_links": sum(link["status"] == "deleted" for link in bucket),
            "total_links": len(bucket), "visits": sum(link["visits"] for link in bucket),
            "secured_links": sum(bool(link["access_code_hash"]) for link in bucket),
        })
    return result


async def get_analytics(user_id: int, days: int = 30) -> dict[str, Any]:
    days = max(1, min(int(days), 365))
    links = await Model_Link.select(columns=RAW_FIELDS, where={"user_id": user_id}, order_by="visits", ascending=False)
    await cleanup_deleted_links(user_id)
    for link in links:
        await expire_link(link["id"])
    links = await Model_Link.select(columns=RAW_FIELDS, where={"user_id": user_id}, order_by="visits", ascending=False)
    now = datetime.now(timezone.utc)
    active = [link for link in links if link["status"] == "active"]
    expired = [link for link in links if link["status"] == "expired"]
    deleted = [link for link in links if link["status"] == "deleted"]
    secured = [link for link in active + expired if link["access_code_hash"]]

    def expiry_minutes(link):
        if link["max_age_minutes"] is None: return None
        return (parse_time(link["created_at"]).timestamp() + link["max_age_minutes"] * 60 - now.timestamp()) / 60

    def deletion_hours(link):
        return (parse_time(link["updated_at"]).timestamp() + 5 * 86400 - now.timestamp()) / 3600

    status_breakdown = [
        {"status": "active", "links": len(active), "visits": sum(link["visits"] for link in active)},
        {"status": "expired", "links": len(expired), "visits": sum(link["visits"] for link in expired)},
        {"status": "deleted", "links": len(deleted), "visits": sum(link["visits"] for link in deleted)},
    ]
    near_expiry = sorted([link for link in active if (value := expiry_minutes(link)) is not None and 0 < value <= 5], key=expiry_minutes)[:5]
    near_deleted = sorted([link for link in deleted if 0 < deletion_hours(link) <= 48], key=deletion_hours)[:5]
    expired_near_deleted = sorted([link for link in expired if 0 < deletion_hours(link) <= 48], key=deletion_hours)[:5]

    return {
        "range_days": days, "range_snapshot": range_snapshot(links, days),
        "totals": {
            "active_links": len(active), "expired_links": len(expired), "deleted_links": len(deleted), "total_links": len(links),
            "total_visits": sum(link["visits"] for link in links), "active_visits": sum(link["visits"] for link in active),
            "expired_visits": sum(link["visits"] for link in expired), "deleted_visits": sum(link["visits"] for link in deleted),
            "secured_links": len(secured), "secured_visits": sum(link["visits"] for link in secured),
        },
        "status_breakdown": status_breakdown, "visits_by_status": status_breakdown,
        "visits_per_link": [chart_link(link, now) for link in links],
        "visits_per_active_link": [chart_link(link, now) for link in active],
        "visits_per_expired_link": [chart_link(link, now) for link in expired],
        "top_links": [chart_link(link, now) for link in links[:5]],
        "secured_links": [chart_link(link, now) for link in secured],
        "near_expiry": [chart_link(link, now) for link in near_expiry],
        "near_deleted": [chart_link(link, now) for link in near_deleted],
        "expired_near_deleted": [chart_link(link, now) for link in expired_near_deleted],
    }
