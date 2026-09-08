from fastapi import APIRouter, Depends, Response, status

from Routers.Analytics.database import get_analytics
from Routers.Auth.middlewares import current_user_id
from Utils.common import api_response

analytics_router = APIRouter(prefix="/api/dashboard/analytics", tags=["Analytics"])


@analytics_router.get("")
async def analytics(days: int = 30, response: Response = None, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        if response: response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Unauthorized", None)
    if days < 1 or days > 365:
        if response: response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "Days must be between 1 and 365", None)
    return api_response(True, "Analytics fetched successfully", await get_analytics(user_id, days))
