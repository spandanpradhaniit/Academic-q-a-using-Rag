from uuid import uuid4
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database.connection import get_db
from app.database.models import (
    ChatFeedback,
    Document,
    KnowledgeBase,
    SearchQuery,
    User,
)
from app.schemas import DeleteAccountInput, LoginInput, UserInput, public_user
from app.services.auth_tokens import (
    RefreshSessionError,
    create_refresh_session,
    csrf_for_refresh_session,
    rotate_refresh_session,
    revoke_refresh_session,
)
from app.rag.indexing import delete_knowledge_base_indexes
from app.services.storage import delete_document_file

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
_REFRESH_COOKIE = "academic_refresh"
_CSRF_COOKIE = "academic_csrf"
_COOKIE_PATH = "/api/auth"


def _set_session_cookies(
    response: Response,
    refresh_token: str,
    csrf_token: str,
    persistent: bool,
) -> None:
    settings = get_settings()
    max_age = (
        settings.refresh_token_expire_days * 24 * 60 * 60
        if persistent
        else None
    )
    cookie_options = {
        "max_age": max_age,
        "secure": settings.refresh_cookie_secure,
        "samesite": settings.refresh_cookie_samesite,
        "path": _COOKIE_PATH,
    }
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        _CSRF_COOKIE,
        csrf_token,
        httponly=False,
        **cookie_options,
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (_REFRESH_COOKIE, _CSRF_COOKIE):
        response.delete_cookie(
            name,
            path=_COOKIE_PATH,
            secure=settings.refresh_cookie_secure,
            httponly=name == _REFRESH_COOKIE,
            samesite=settings.refresh_cookie_samesite,
        )


def _raise_session_error(exc: RefreshSessionError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a student account",
)
def register(
    payload: UserInput,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )
    user = User(
        id=str(uuid4()),
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role="student",
        is_active=True,
    )
    db.add(user)
    try:
        access_token = create_access_token(user.id)
        refresh_token, csrf_token = create_refresh_session(db, user)
        db.commit()
    except Exception as exc:
        db.rollback()
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists",
            ) from exc
        raise
    _set_session_cookies(response, refresh_token, csrf_token, persistent=True)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": public_user(user),
    }


@router.post("/login", summary="Log in and receive an access token")
def login(
    payload: LoginInput,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    email = str(payload.email).strip().lower()
    user = db.scalar(
        select(User).where(User.email == email, User.is_active.is_(True))
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")

    access_token = create_access_token(user.id)
    refresh_token, csrf_token = create_refresh_session(
        db,
        user,
        persistent=payload.remember,
    )
    db.commit()
    _set_session_cookies(
        response,
        refresh_token,
        csrf_token,
        persistent=payload.remember,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": public_user(user),
    }


@router.get("/csrf", summary="Get the current session's CSRF token")
def get_csrf_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        csrf_token = csrf_for_refresh_session(
            db,
            request.cookies.get(_REFRESH_COOKIE),
            request.cookies.get(_CSRF_COOKIE),
        )
    except RefreshSessionError as exc:
        _raise_session_error(exc)
    return {"csrf_token": csrf_token}


@router.post("/refresh", summary="Rotate the refresh token")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        access_token, refresh_token, csrf_token, persistent = rotate_refresh_session(
            db,
            request.cookies.get(_REFRESH_COOKIE),
            request.cookies.get(_CSRF_COOKIE),
            request.headers.get("x-csrf-token"),
        )
    except RefreshSessionError as exc:
        if exc.status_code == 401:
            _clear_session_cookies(response)
        _raise_session_error(exc)
    _set_session_cookies(response, refresh_token, csrf_token, persistent)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
    }


@router.get("/me", summary="Get the current user")
def me(user: CurrentUser):
    return public_user(user)


@router.post("/logout", summary="Revoke the current refresh-token family")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if refresh_token:
        try:
            revoke_refresh_session(
                db,
                refresh_token,
                request.cookies.get(_CSRF_COOKIE),
                request.headers.get("x-csrf-token"),
            )
        except RefreshSessionError as exc:
            _raise_session_error(exc)
    _clear_session_cookies(response)
    return {"success": True}


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete the account and its data",
)
def delete_account(
    payload: DeleteAccountInput,
    response: Response,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Password is incorrect")

    documents = db.scalars(
        select(Document).where(Document.user_id == user.id)
    ).all()
    knowledge_bases = db.scalars(
        select(KnowledgeBase).where(KnowledgeBase.user_id == user.id)
    ).all()
    try:
        for document in documents:
            delete_document_file(document.file_path)
        for knowledge_base in knowledge_bases:
            asyncio.run(
                delete_knowledge_base_indexes(
                    knowledge_base.id,
                    knowledge_base.vector_store,
                )
            )
    except Exception as exc:
        logger.exception("Failed to fully clean data for user %s", user.id)
        raise HTTPException(
            status_code=503,
            detail="Account data cleanup is incomplete. Retry account deletion.",
        ) from exc

    db.execute(delete(SearchQuery).where(SearchQuery.user_id == user.id))
    db.execute(delete(ChatFeedback).where(ChatFeedback.user_id == user.id))
    db.delete(user)
    db.commit()
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
