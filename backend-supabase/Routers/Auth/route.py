import re

from fastapi import APIRouter, Depends, Header, Response, status

from Routers.Auth.database import (
    create_session, create_user, delete_session, find_user_by_email,
    find_user_by_id, update_password, update_profile, user_exists,
)
from Routers.Auth.datamodels import LoginRequest, PasswordUpdateRequest, ProfileUpdateRequest, SignupRequest
from Routers.Auth.middlewares import bearer_token, current_user_id
from Models.Model_LoginEvent import Model_LoginEvent
from Utils.common import api_response, create_session_token, hash_password, session_expiry


auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])


def conflict_error(error: Exception) -> bool:
    return "duplicate" in str(error).lower() or "unique" in str(error).lower()


@auth_router.post("/signup")
async def signup(payload: SignupRequest, response: Response):
    username, email, password = payload.username.strip(), payload.email.strip().lower(), payload.password.strip()
    if not username or not email or not password:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "Username, email and password are required", None)
    if len(password) < 6:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "Password must be at least 6 characters", None)
    if await user_exists(username, email):
        response.status_code = status.HTTP_409_CONFLICT
        return api_response(False, "User already exists", None)
    try:
        user = await create_user(username, email, password)
    except Exception as error:
        if not conflict_error(error):
            raise
        response.status_code = status.HTTP_409_CONFLICT
        return api_response(False, "User already exists", None)
    token = create_session_token()
    await create_session(user["id"], token, session_expiry())
    return api_response(True, "User created successfully", {**user, "userId": user["id"], "token": token})


@auth_router.post("/login")
async def login(payload: LoginRequest, response: Response):
    email, password = payload.email.strip().lower(), payload.password.strip()
    user = await find_user_by_email(email, include_password=True) if email and password else None
    if not user or user["password_hash"] != hash_password(password):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Invalid email or password", None)
    token = create_session_token()
    await create_session(user["id"], token, session_expiry())
    await Model_LoginEvent.insert({"user_id": user["id"]})
    return api_response(True, "Login successful", {"userId": user["id"], "token": token})


@auth_router.get("/me")
async def me(response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Unauthorized", None)
    user = await find_user_by_id(user_id)
    if not user:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "User not found", None)
    return api_response(True, "Authenticated user", user)


@auth_router.post("/logout")
async def logout(response: Response, authorization: str | None = Header(default=None)):
    token = bearer_token(authorization)
    if not token:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Unauthorized", None)
    if not await delete_session(token):
        response.status_code = status.HTTP_404_NOT_FOUND
        return api_response(False, "No active session found", None)
    return api_response(True, "Logged out successfully", None)


@auth_router.patch("/profile")
async def profile(payload: ProfileUpdateRequest, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Unauthorized", None)
    username, email = payload.username.strip(), payload.email.strip().lower()
    if not username or not email:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "Username and email are required", None)
    existing = await find_user_by_email(email)
    if existing and existing["id"] != user_id:
        response.status_code = status.HTTP_409_CONFLICT
        return api_response(False, "Email is already in use", None)
    try:
        updated = await update_profile(user_id, username, email)
    except Exception as error:
        if not conflict_error(error):
            raise
        response.status_code = status.HTTP_409_CONFLICT
        return api_response(False, "Username or email is already in use", None)
    return api_response(True, "Profile updated successfully", updated)


@auth_router.patch("/password")
async def password(payload: PasswordUpdateRequest, response: Response, user_id: int | None = Depends(current_user_id)):
    if not user_id:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Unauthorized", None)
    user = await find_user_by_id(user_id, include_password=True)
    if not user or user["password_hash"] != hash_password(payload.old_password):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return api_response(False, "Current password is incorrect", None)
    if len(payload.new_password) < 6:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "New password must be at least 6 characters", None)
    if payload.new_password != payload.confirm_password:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return api_response(False, "New passwords do not match", None)
    await update_password(user_id, payload.new_password)
    return api_response(True, "Password updated successfully", None)
