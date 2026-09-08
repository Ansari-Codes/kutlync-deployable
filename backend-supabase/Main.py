from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from Routers.Analytics.route import analytics_router
from Routers.Auth.middlewares import current_user_id
from Routers.Auth.route import auth_router
from Routers.Links.database import dashboard_stats
from Routers.Links.route import links_router
from Models.Model_Link import Model_Link
from Models.Model_User import Model_User
from Models.Model_LoginEvent import Model_LoginEvent
from Utils.common import api_response

load_dotenv()

app = FastAPI(title="KutLynk API - Supabase")
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
@app.get("/api/health")
async def health():
    return api_response(True, "Healthy", {"status": "ok"})


@app.get("/api/dashboard/stats")
async def stats(user_id: int | None = Depends(current_user_id)):
    if not user_id:
        return api_response(False, "Unauthorized", None)
    return api_response(True, "Dashboard stats fetched", await dashboard_stats(user_id))


@app.get("/api/satatistics")
@app.get("/api/statistics")
async def statistics():
    links = await Model_Link.select(columns="visits")
    users = await Model_User.select(columns="id")
    logins = await Model_LoginEvent.select(columns="id")
    return api_response(True, "Statistics fetched successfully", {
        "total_links": len(links),
        "total_users": len(users),
        "total_visits": sum(int(link.get("visits", 0)) for link in links),
        "total_log_ins": len(logins),
    })


app.include_router(auth_router)
app.include_router(links_router)
app.include_router(analytics_router)
