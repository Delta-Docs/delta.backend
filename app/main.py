from fastapi import FastAPI
from app.api import api_router
from app.utils.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Hello from Delta Backend :)"}
