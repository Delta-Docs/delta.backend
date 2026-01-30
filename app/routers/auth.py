from datetime import timedelta
from fastapi import APIRouter, Depends, Response, Request, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db_connection
from app import schemas
from app.models.user import User
from app.utils import auth_utils
from app.utils.config import settings

router = APIRouter()

@router.post("/signup", response_model=schemas.Message)
def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db_connection)
):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists.",
        )
    
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=auth_utils.get_hash(user_in.password),
    )
    
    db.add(user)
    db.commit()
    return {"message": "User created successfully"}

@router.post("/login", response_model=schemas.Message)
def login(
    response: Response,
    user_in: schemas.UserLogin,
    db: Session = Depends(get_db_connection)
):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not auth_utils.verify_hash(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect credentials."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_utils.create_access_token(user.id, expires_delta=access_token_expires)
    
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = auth_utils.create_refresh_token(user.id, expires_delta=refresh_token_expires)
    
    user.current_refresh_token_hash = auth_utils.get_hash(refresh_token)
    db.commit()
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=int(access_token_expires.total_seconds()),
        expires=int(access_token_expires.total_seconds()),
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=int(refresh_token_expires.total_seconds()),
        expires=int(refresh_token_expires.total_seconds()),
    )
    
    return {"message": "Login successful"}

@router.post("/logout", response_model=schemas.Message)
def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db_connection)
):
    user_id = None
    
    access_token = request.cookies.get("access_token")
    if access_token:
        payload = auth_utils.verify_token(access_token)
        if payload:
            user_id = payload.get("sub")
            
    if not user_id:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            payload = auth_utils.verify_token(refresh_token)
            if payload:
                user_id = payload.get("sub")
    
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.current_refresh_token_hash = None
            db.commit()
            
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    
    return {"message": "Logout successful"}
