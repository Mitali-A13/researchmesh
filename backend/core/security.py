from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.auth import verify_access_token
from backend.db.database import SessionLocal
from backend.db.models import User

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_access_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


def get_db_user(current_user: dict, db: Session):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
