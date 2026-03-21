"""Admin API router — all /admin/v1/* endpoints."""
from fastapi import APIRouter
from app.admin.api import (
    auth as admin_auth,
    overview, users, agent_monitor, support,
    revenue, costs, coupons, system as sys_admin,
)

router = APIRouter()

router.include_router(admin_auth.router, prefix="/auth", tags=["admin-auth"])
router.include_router(overview.router, prefix="/v1/overview", tags=["admin-overview"])
router.include_router(users.router, prefix="/v1/users", tags=["admin-users"])
router.include_router(agent_monitor.router, prefix="/v1/agent", tags=["admin-agent"])
router.include_router(support.router, prefix="/v1", tags=["admin-support"])
router.include_router(revenue.router, prefix="/v1/revenue", tags=["admin-revenue"])
router.include_router(costs.router, prefix="/v1/costs", tags=["admin-costs"])
router.include_router(coupons.router, prefix="/v1/coupons", tags=["admin-coupons"])
router.include_router(sys_admin.router, prefix="/v1/system", tags=["admin-system"])
