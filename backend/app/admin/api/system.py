"""Admin system — health, config, env info."""
import os, sys
from fastapi import APIRouter, Depends
from app.admin.api.auth import require_permission, AdminUser

router = APIRouter()

@router.get("/health")
async def system_health(admin: AdminUser = Depends(require_permission("overview.read"))):
    return {
        "api": "healthy",
        "python": sys.version,
        "env": os.getenv("ENVIRONMENT","unknown"),
        "region": os.getenv("AWS_REGION","us-east-1"),
    }

@router.get("/config")
async def system_config(admin: AdminUser = Depends(require_permission("system.read"))):
    """Return non-sensitive config info."""
    return {
        "anthropic_model": os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-20250514"),
        "ats_threshold": float(os.getenv("ATS_MATCH_THRESHOLD","0.65")),
        "cycle_interval_hours": int(os.getenv("CYCLE_INTERVAL_HOURS","4")),
        "max_apply_per_cycle": int(os.getenv("MAX_APPLY_PER_CYCLE","10")),
        "resume_storage_months": int(os.getenv("RESUME_STORAGE_MONTHS","6")),
    }
