from fastapi import APIRouter
from app.routers import auth, system

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(system.router, tags=["System"])
