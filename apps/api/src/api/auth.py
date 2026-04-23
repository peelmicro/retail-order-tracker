from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.deps import get_current_user
from src.application.dtos import CamelModel
from src.domain.user import User, UserRole
from src.infrastructure.auth.jwt_service import create_access_token
from src.infrastructure.auth.user_store import user_store

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(CamelModel):
    username: str
    email: str
    role: UserRole


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    user = user_store.get_by_username(form.username)
    if user is None or not user_store.verify_password(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    token = create_access_token(
        subject=user.username,
        extra_claims={"role": user.role.value},
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
    )
