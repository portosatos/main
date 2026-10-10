"""Server-side sessions (SPEC F1): the browser holds a random token in the ht_session cookie, the
database holds sha256(token). Lifetime is 14 days from login by Clock, not extended (ADR-026)."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthSession, User

SESSION_COOKIE = "ht_session"
SESSION_TTL = timedelta(days=14)
# last_seen_at is informational: refresh it at most this often to avoid a write per request.
LAST_SEEN_RESOLUTION = timedelta(minutes=1)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> str:
    """Add a session row and return its token (the cookie value). The caller commits."""
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            id=token_hash(token),
            user_id=user_id,
            created_at=now,
            expires_at=now + SESSION_TTL,
            last_seen_at=now,
        )
    )
    return token


async def resolve_session(db: AsyncSession, token: str, now: datetime) -> User | None:
    """The user of a live session, or None. An expired session is deleted on the spot."""
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.id == token_hash(token))
        )
    ).first()
    if row is None:
        return None
    auth_session, user = row
    if auth_session.expires_at <= now:
        await db.delete(auth_session)
        await db.commit()
        return None
    if now - auth_session.last_seen_at >= LAST_SEEN_RESOLUTION:
        auth_session.last_seen_at = now
        await db.commit()
    return user


async def delete_session(db: AsyncSession, token: str) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.id == token_hash(token)))
    await db.commit()


def set_session_cookie(response: Response, token: str, *, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=secure)
