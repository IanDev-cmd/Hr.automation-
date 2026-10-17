"""Desk JWTs. Home managers only see the home named in the token."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.config import get_settings

ROLES = {"HR_ADMIN", "HOME_MANAGER"}


@dataclass
class DeskUser:
    username: str
    role: str
    home_name: str


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def issue_token(username: str, role: str, home_name: str = "", ttl_seconds: int = 60 * 60 * 12) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(
        json.dumps(
            {
                "sub": username,
                "role": role,
                "home": home_name,
                "iat": now,
                "exp": now + ttl_seconds,
            }
        ).encode()
    )
    signing = f"{header}.{payload}".encode()
    signature = hmac.new(get_settings().jwt_secret.encode(), signing, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def decode_token(token: str) -> DeskUser:
    try:
        header, payload, signature = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Sign in is required") from exc
    signing = f"{header}.{payload}".encode()
    expected = hmac.new(get_settings().jwt_secret.encode(), signing, hashlib.sha256).digest()
    if not hmac.compare_digest(_unb64(signature), expected):
        raise HTTPException(status_code=401, detail="Sign in is required")
    data = json.loads(_unb64(payload))
    if int(data.get("exp") or 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Sign in has expired")
    role = data.get("role")
    if role not in ROLES:
        raise HTTPException(status_code=401, detail="Sign in is required")
    return DeskUser(username=str(data.get("sub") or ""), role=role, home_name=str(data.get("home") or ""))


def current_user(request: Request) -> DeskUser:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in is required")
    return decode_token(header.split(" ", 1)[1].strip())


def assert_home(user: DeskUser, home_name: str) -> None:
    if user.role == "HR_ADMIN":
        return
    if user.role == "HOME_MANAGER" and user.home_name == home_name:
        return
    raise HTTPException(status_code=403, detail="This home is outside your scope")
