from pydantic import BaseModel


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    username: str
    email: str


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str
