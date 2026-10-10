"""/api/auth: register, login, logout, me (SPEC F1, §6.3)."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import ClockDep, SessionDep
from app.auth.accounts import EmailTakenError, authenticate, create_user
from app.auth.deps import CurrentUserDep
from app.auth.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    set_session_cookie,
)
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def secure_cookies(request: Request) -> bool:
    # Secure only in prod: the dev stack is served over plain http.
    return request.app.state.settings.app_env == "prod"


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, request: Request, response: Response, db: SessionDep, clock: ClockDep
) -> UserOut:
    """Create the account and log in right away."""
    now = await clock.now()
    try:
        user = await create_user(
            db, email=body.email, password=body.password, timezone=body.timezone, now=now
        )
    except EmailTakenError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Этот email уже зарегистрирован"
        ) from None
    token = create_session(db, user.id, now)
    await db.commit()
    set_session_cookie(response, token, secure=secure_cookies(request))
    return UserOut.model_validate(user)


@router.post("/login")
async def login(
    body: LoginRequest, request: Request, response: Response, db: SessionDep, clock: ClockDep
) -> UserOut:
    user = await authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    token = create_session(db, user.id, await clock.now())
    await db.commit()
    set_session_cookie(response, token, secure=secure_cookies(request))
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, db: SessionDep) -> Response:
    """End the session of the cookie. Without a (valid) session it is a no-op."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await delete_session(db, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, secure=secure_cookies(request))
    return response


@router.get("/me")
async def me(user: CurrentUserDep) -> UserOut:
    return UserOut.model_validate(user)
