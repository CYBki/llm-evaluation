from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import DuplicateEmailError
from app.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services.auth_service import authenticate_user, create_user

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni kullanıcı kaydı",
    description="E-posta ve şifre ile kayıt olur, API key döner. Bu key tüm endpoint'lerde `X-API-Key` header'ı olarak kullanılır.",
    responses={
        201: {"description": "Kayıt başarılı, API key döner"},
        409: {"description": "E-posta zaten kayıtlı"},
        422: {"description": "Geçersiz istek (validation hatası)"},
        429: {"description": "Rate limit aşıldı"},
    },
)
@limiter.limit("3/minute")
def register(
    request: Request, payload: RegisterRequest, db: Session = Depends(get_db)
) -> RegisterResponse:
    """Yeni kullanıcı oluşturur ve API key üretir."""
    try:
        user, api_key = create_user(db, payload.email, payload.password)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        api_key=api_key,
        api_key_prefix=user.api_key_prefix,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Kullanıcı girişi",
    description="E-posta ve şifre ile giriş yapar. API key prefix'ini döner (tam key sadece register'da verilir).",
    responses={
        200: {"description": "Giriş başarılı"},
        401: {"description": "Geçersiz kimlik bilgileri"},
        429: {"description": "Rate limit aşıldı"},
    },
)
@limiter.limit("5/minute")
def login(
    request: Request, payload: LoginRequest, db: Session = Depends(get_db)
) -> LoginResponse:
    """Mevcut kullanıcı ile giriş yapar."""
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return LoginResponse(
        user_id=str(user.id),
        email=user.email,
        api_key_prefix=user.api_key_prefix,
    )
