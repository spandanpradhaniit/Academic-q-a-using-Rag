from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.database.models import RefreshToken, User


class RefreshSessionError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_refresh_session(
    db: Session,
    user: User,
    persistent: bool = True,
    family_id: str | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    refresh_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    db.add(
        RefreshToken(
            id=str(uuid4()),
            user_id=user.id,
            family_id=family_id or str(uuid4()),
            token_hash=_hash(refresh_token),
            csrf_hash=_hash(csrf_token),
            persistent=persistent,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    db.flush()
    return refresh_token, csrf_token


def _get_session(
    db: Session,
    refresh_token: str,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> RefreshToken:
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == _hash(refresh_token))
        .with_for_update()
    )
    if not row:
        raise RefreshSessionError("INVALID_REFRESH_TOKEN", "Refresh session is invalid.", 401)
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise RefreshSessionError("CSRF_FAILED", "CSRF token is missing or invalid.", 403)
    if not hmac.compare_digest(row.csrf_hash, _hash(csrf_cookie)):
        raise RefreshSessionError("CSRF_FAILED", "CSRF token is missing or invalid.", 403)
    return row


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def rotate_refresh_session(
    db: Session,
    refresh_token: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> tuple[str, str, str, bool]:
    if not refresh_token:
        raise RefreshSessionError("INVALID_REFRESH_TOKEN", "Refresh session is invalid.", 401)
    row = _get_session(db, refresh_token, csrf_cookie, csrf_header)
    if row.revoked_at:
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == row.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        db.commit()
        raise RefreshSessionError(
            "REFRESH_TOKEN_REUSE",
            "Refresh token reuse detected; sign in again.",
            401,
        )
    if _is_expired(row.expires_at):
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise RefreshSessionError("INVALID_REFRESH_TOKEN", "Refresh session has expired.", 401)

    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise RefreshSessionError("INVALID_REFRESH_TOKEN", "User account is unavailable.", 401)

    row.revoked_at = datetime.now(timezone.utc)
    next_token, next_csrf = create_refresh_session(
        db,
        user,
        persistent=row.persistent,
        family_id=row.family_id,
    )
    replacement = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(next_token))
    )
    if replacement is None:
        raise RuntimeError("Failed to create the rotated refresh session.")
    row.replaced_by_id = replacement.id
    db.commit()
    return create_access_token(user.id), next_token, next_csrf, row.persistent


def revoke_refresh_session(
    db: Session,
    refresh_token: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    if not refresh_token:
        return
    row = _get_session(db, refresh_token, csrf_cookie, csrf_header)
    now = datetime.now(timezone.utc)
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.family_id == row.family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()


def csrf_for_refresh_session(
    db: Session,
    refresh_token: str | None,
    csrf_cookie: str | None,
) -> str:
    if not refresh_token or not csrf_cookie:
        raise RefreshSessionError(
            "INVALID_REFRESH_TOKEN",
            "Refresh session is invalid.",
            401,
        )
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(refresh_token))
    )
    if (
        not row
        or row.revoked_at
        or _is_expired(row.expires_at)
        or not hmac.compare_digest(row.csrf_hash, _hash(csrf_cookie))
    ):
        raise RefreshSessionError(
            "INVALID_REFRESH_TOKEN",
            "Refresh session is invalid.",
            401,
        )
    return csrf_cookie
