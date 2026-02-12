from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.services.auth_service import create_user

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    user, api_key = create_user(db, payload.email, payload.password)
    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        api_key=api_key,
        api_key_prefix=user.api_key_prefix,
    )
