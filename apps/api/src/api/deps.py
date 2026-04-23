from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from src.domain.user import User
from src.infrastructure.auth.jwt_service import decode_token
from src.infrastructure.auth.user_store import user_store

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not isinstance(username, str):
            raise credentials_exception
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    user = user_store.get_by_username(username)
    if user is None or not user.is_active:
        raise credentials_exception
    return user
