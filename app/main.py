from fastapi import FastAPI
from app.core.config import settings
from app.api import endpoints

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(endpoints.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Hello from Delta Backend :)"}
