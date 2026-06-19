"""Authentication service: password hashing, JWT tokens, user management."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import log_event
from app.models import RefreshToken, User

logger = logging.getLogger("app.auth")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, db: Session) -> str:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    rt = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(rt)
    db.commit()

    return raw_token


def decode_access_token(token: str) -> str | None:
    """Returns user_id if valid, None otherwise."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def refresh_access_token(raw_token: str, db: Session) -> tuple[str, str] | None:
    """Validate refresh token, rotate it, return (new_access, new_refresh) or None."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    now = datetime.now(UTC).replace(tzinfo=None)
    if not rt or rt.expires_at < now:
        if rt:
            db.delete(rt)
            db.commit()
        return None

    db.delete(rt)
    db.commit()

    new_access = create_access_token(rt.user_id)
    new_refresh = create_refresh_token(rt.user_id, db)
    return new_access, new_refresh


def revoke_refresh_token(raw_token: str, db: Session) -> bool:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if rt:
        db.delete(rt)
        db.commit()
        return True
    return False


def register_user(email: str, password: str, display_name: str | None, db: Session) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        log_event(logger, logging.WARNING, "register_duplicate", email=email.lower().strip())
        raise ValueError("Email already registered")

    user = User(
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event(logger, logging.INFO, "user_registered", user_id=user.id, email=user.email)
    return user


def authenticate_user(email: str, password: str, db: Session) -> User | None:
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.hashed_password):
        log_event(logger, logging.WARNING, "login_failed", email=email.lower().strip())
        return None
    user.last_login_at = datetime.now(UTC)
    db.commit()
    log_event(logger, logging.INFO, "login_success", user_id=user.id, email=user.email)
    return user


def get_user_by_id(user_id: str, db: Session) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
