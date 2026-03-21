from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT, "version": "1.0.0"}


@router.get("/", tags=["health"])
async def root():
    return {"name": "JobAimer API", "status": "running"}
