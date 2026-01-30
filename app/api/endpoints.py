from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app import schemas
from app.models.user import User
from app.core import utils

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "pong :)"}

@router.post("/signup", response_model=schemas.Message)
def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(deps.get_db)
):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        return JSONResponse(
            status_code=400,
            content={"message": "User with this email already exists."},
        )
    
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=utils.get_password_hash(user_in.password),
    )
    
    db.add(user)
    db.commit()
    return {"message": "User created successfully"}
