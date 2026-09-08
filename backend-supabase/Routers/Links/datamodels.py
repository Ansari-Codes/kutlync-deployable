from typing import Literal
from pydantic import BaseModel, Field


class LinkRequest(BaseModel):
    link_name: str | None = Field(default=None, max_length=50)
    link_description: str | None = Field(default=None, max_length=150)
    destination_link: str | None = None
    slug: str | None = None
    max_age_minutes: int | None = None
    access_code: str | None = None
    status: Literal["active", "deleted", "expired"] | None = None
    security_action: Literal["keep", "remove", "update"] = "keep"


class FilterQuery(BaseModel):
    q: str | None = None
    ascen: bool = True
    sort_by: Literal["id", "link_name", "destination_link", "slug", "visits", "max_age_minutes", "created_at", "updated_at", "status"] = "updated_at"
    status: Literal["active", "deleted", "expired"] | None = None
    limit: int = -1


class VerifyRequest(BaseModel):
    access_code: str | None = None
