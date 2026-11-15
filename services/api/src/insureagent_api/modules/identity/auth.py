import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from insureagent_persistence.store import accounts, sessions
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, insert, select

router = APIRouter(prefix="/v1", tags=["identity"])
bearer = HTTPBearer(auto_error=False)


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    salt = base64.b64decode(stored)[:16]
    return hmac.compare_digest(password_hash(password, salt), stored)


def store_for(request: Request):
    if request.app.state.store is None:
        raise HTTPException(503, "alpha_not_configured")
    return request.app.state.store


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    store = store_for(request)
    if credentials is None:
        raise HTTPException(401, "authentication_required")
    with store.transaction() as conn:
        row = (
            conn.execute(
                select(sessions).where(
                    sessions.c.token_hash == token_hash(credentials.credentials),
                    sessions.c.expires_at > datetime.now(timezone.utc).isoformat(),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(401, "session_invalid")
        return row["tenant_id"]


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


@router.post("/sessions")
def login(body: Login, request: Request):
    store = store_for(request)
    # Alpha is private/local only. Accounts are provisioned via CLI, not public registration.
    with store.transaction() as conn:
        account = (
            conn.execute(select(accounts).where(accounts.c.username == body.username))
            .mappings()
            .first()
        )
        dummy = password_hash("invalid-password", b"0" * 16)
        valid = verify_password(body.password, account["password_hash"] if account else dummy)
        if not account or not valid:
            raise HTTPException(401, "invalid_credentials")
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        conn.execute(
            insert(sessions).values(
                token_hash=token_hash(token), tenant_id=account["id"], expires_at=expiry
            )
        )
        return {"access_token": token, "token_type": "bearer", "expires_at": expiry}


@router.delete("/sessions/current", status_code=204)
def logout(request: Request, tenant=Depends(principal), credentials=Depends(bearer)):
    with store_for(request).transaction() as conn:
        conn.execute(
            delete(sessions).where(
                sessions.c.tenant_id == tenant,
                sessions.c.token_hash == token_hash(credentials.credentials),
            )
        )
