from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.routes.deps import get_db, get_current_user, get_db_user
from backend.db.models import User
from backend.auth import hash_password, verify_password, create_access_token

from backend.schemas.auth import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
    MeResponse,
)

from backend.schemas.history import MessageResponse

router = APIRouter(tags=["Auth"])


# sign-up
@router.post(
    "/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == data.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered.")

    new_user = User(
        name=data.name.strip(),
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
    )

    db.add(new_user)
    db.commit()

    return {"success": True, "message": "Account created successfully."}


# login
@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials.")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials.")
    token = create_access_token({"sub": user.email, "user_id": user.id})
    return {"success": True, "access_token": token, "token_type": "bearer"}


# user info
@router.get("/me", response_model=MeResponse)
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user(current_user, db)

    return {
        "success": True,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    }


# change password route
@router.put("/change-password", response_model=MessageResponse)
def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user(current_user, db)

    # Verify old password
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    # Prevent same password reuse
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="New password must be different.")

    # Hash new password
    user.hashed_password = hash_password(data.new_password)

    db.commit()

    return {"success": True, "message": "Password changed successfully."}
