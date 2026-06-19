"""Authentication endpoints: register, login, refresh, logout, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(req.email, req.password, req.display_name, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(req.email, req.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh")
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    result = refresh_access_token(req.refresh_token, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    access_token, new_refresh = result
    return {"access_token": access_token, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
def logout(req: RefreshRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(req.refresh_token, db)
    return {"message": "Logged out"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
