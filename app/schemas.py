from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List


class APIResponse(BaseModel):
    ok: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class AccountCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    session_string: str
    is_enabled: bool = True


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    session_string: Optional[str] = None
    is_enabled: Optional[bool] = None


class GroupSelect(BaseModel):
    chat_ids: List[int] = Field(default_factory=list)


class CollectRequest(BaseModel):
    days: int = 7
    accounts: Optional[List[int]] = None


class ExportQuery(BaseModel):
    range: str
    account_id: Optional[int] = None
    chat_id: Optional[int] = None


# Session generation
class SessionInitRequest(BaseModel):
    phone: str


class SessionVerifyRequest(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None


# Authentication
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"