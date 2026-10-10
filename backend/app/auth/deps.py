"""The current_user dependency: the user of the ht_session cookie, or 401."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import ClockDep, SessionDep
from app.auth.sessions import SESSION_COOKIE, resolve_session
from app.models import User


async def current_user(request: Request, db: SessionDep, clock: ClockDep) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user = await resolve_session(db, token, await clock.now()) if token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    return user


CurrentUserDep = Annotated[User, Depends(current_user)]
