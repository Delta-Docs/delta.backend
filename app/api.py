from fastapi import APIRouter
from app.routers import auth, webhooks, repos, dashboard

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])
api_router.include_router(repos.router, prefix="/repos", tags=["Repositories"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])