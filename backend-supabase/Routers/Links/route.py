from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response, status

from Models.Model_Link import Model_Link
from Routers.Auth.middlewares import current_user_id
from Routers.Links.database import (
    create_link, get_link, get_link_by_slug, get_raw_link,
)
from Routers.Links.database import list_links, restore_link, update_link
from Routers.Links.datamodels import FilterQuery, LinkRequest, VerifyRequest
from Utils.common import api_response, hash_password

links_router = APIRouter(tags=["Links"])
verification_attempts: dict[str, list[float]] = defaultdict(list)


def unauthorized(response: Response):
    response.status_code = status.HTTP_401_UNAUTHORIZED
    return api_response(False, "Unauthorized", None)


def normalize_destination(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname or "." not in parsed.hostname:
        return None
    return candidate if "://" in candidate else f"https://{candidate}"


def clean_payload(payload: LinkRequest) -> dict:
    values = payload.model_dump(exclude_unset=True)
    for field in ("link_name", "link_description", "destination_link", "slug"):
        if field in values and values[field] is not None:
            values[field] = values[field].strip()
    return values


@links_router.get("/api/dashboard/links")
async def links(response: Response, user_id: int | None = Depends(current_user_id), filters: FilterQuery = Depends()):
    if not user_id:
        return unauthorized(response)
    rows = await list_links(user_id, include_deleted=filters.status == "deleted")
    if filters.status:
        rows = [row for row in rows if row["status"] == filters.status]
    if filters.q:
        query = filters.q.lower()
        rows = [row for row in rows if any(query in str(row.get(field, "")).lower() for field in ("link_name", "destination_link", "slug"))]
    rows.sort(key=lambda row: row.get(filters.sort_by), reverse=not filters.ascen)
    return api_response(True, "Links fetched successfully", rows[:filters.limit] if filters.limit > 0 else rows)


@links_router.post("/api/dashboard/links")
async def add_link(payload: LinkRequest, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return unauthorized(response)
    values = clean_payload(payload)
    destination = normalize_destination(values.get("destination_link"))
    if not destination:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "A valid destination link is required", None)
    values["destination_link"] = destination
    values.setdefault("link_name", urlparse(destination).hostname or "Untitled link")
    values.setdefault("link_description", "")
    if values.get("max_age_minutes") is not None and values["max_age_minutes"] <= 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "Max age must be a positive number of minutes", None)
    try:
        link = await create_link(user_id, values)
    except Exception as error:
        if "duplicate" not in str(error).lower() and "unique" not in str(error).lower():
            raise
        response.status_code = status.HTTP_409_CONFLICT
        return api_response(False, "Slug already exists", None)
    if not values.get("slug"):
        link_id = link["id"]
        await Model_Link.update({"slug": f"link{link_id}"}, {"id": link_id})
        link = await get_link(link_id, user_id)
    return api_response(True, "Link created successfully", link)


@links_router.get("/api/dashboard/links/{link_id}")
async def view_link(link_id: int, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return unauthorized(response)
    link = await get_link(link_id, user_id)
    if not link:
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Link not found", None)
    return api_response(True, "Link fetched successfully", link)


@links_router.patch("/api/dashboard/links/{link_id}")
async def edit_link(link_id: int, payload: LinkRequest, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return unauthorized(response)
    if not await get_raw_link(link_id, user_id):
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Link not found", None)
    values = clean_payload(payload)
    if "destination_link" in values:
        values["destination_link"] = normalize_destination(values["destination_link"])
        if not values["destination_link"]:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return api_response(False, "A valid destination link is required", None)
    try:
        link = await update_link(link_id, user_id, values)
    except Exception as error:
        if "duplicate" not in str(error).lower() and "unique" not in str(error).lower():
            raise
        response.status_code = status.HTTP_409_CONFLICT
        return api_response(False, "Slug already exists", None)
    return api_response(True, "Link updated successfully", link)


@links_router.delete("/api/dashboard/links/{link_id}")
async def delete_link(link_id: int, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return unauthorized(response)
    changed = await Model_Link.update({"status": "deleted", "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}, {"id": link_id, "user_id": user_id})
    if not changed:
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Link not found", None)
    return api_response(True, "Link deleted successfully", None)


@links_router.patch("/api/dashboard/links/{link_id}/restore")
async def restore(link_id: int, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return unauthorized(response)
    link = await restore_link(link_id, user_id)
    if not link:
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Deleted link not found", None)
    return api_response(True, "Link restored successfully", link)


@links_router.delete("/api/dashboard/links/{link_id}/permanent")
async def permanent_delete(link_id: int, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return unauthorized(response)
    changed = await Model_Link.delete({"id": link_id, "user_id": user_id})
    if not changed:
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Deleted link not found", None)
    return api_response(True, "Link permanently deleted", None)


@links_router.get("/api/visit/is_secured")
async def is_secured(slug: str, response: Response):
    link = await get_link_by_slug(slug)
    if not link:
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Link not found", None)
    return api_response(True, "Link fetched successfully", {"is_secured": bool(link.get("access_code_hash"))})


@links_router.post("/api/visits/verify")
async def verify(slug: str, payload: VerifyRequest, request: Request, response: Response):
    link = await get_link_by_slug(slug)
    if not link or link["status"] != "active":
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "Link not found", None)
    if link["max_age_minutes"] is not None:
        created = datetime.fromisoformat(link["created_at"].replace(" ", "T").replace("Z", "+00:00"))
        if (datetime.now(created.tzinfo) - created).total_seconds() >= link["max_age_minutes"] * 60:
            response.status_code = status.HTTP_410_GONE
            return api_response(False, "Link has expired", None)
    if link["access_code_hash"]:
        key = f"{request.client.host if request.client else 'unknown'}:{slug}"
        now = time.time()
        verification_attempts[key] = [stamp for stamp in verification_attempts[key] if now - stamp < 60]
        if len(verification_attempts[key]) >= 5:
            response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
            return api_response(False, "Too many attempts. Try again in a minute", None)
        verification_attempts[key].append(now)
        if not payload.access_code or hash_password(payload.access_code) != link["access_code_hash"]:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return api_response(False, "Invalid access code", None)
    await Model_Link.update({"visits": link["visits"] + 1, "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}, {"id": link["id"]})
    return api_response(True, "Link verified", {"destination_link": link["destination_link"]})
