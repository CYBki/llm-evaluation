import hashlib
import secrets

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _generate_api_key() -> str:
    return f"re_{secrets.token_urlsafe(32)}"


def create_user(db: Session, email: str, password: str) -> tuple[User, str]:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    api_key = _generate_api_key()
    user = User(
        email=email,
        hashed_password=pwd_context.hash(password),
        api_key_hash=_hash_api_key(api_key),
        api_key_prefix=api_key[:8],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, api_key


def get_user_by_api_key(db: Session, api_key: str) -> User | None:
    hashed = _hash_api_key(api_key)
    return db.query(User).filter(User.api_key_hash == hashed, User.is_active.is_(True)).first()
