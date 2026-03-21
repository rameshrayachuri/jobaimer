"""Admin API — combines all admin sub-routers under /admin prefix."""
from fastapi import APIRouter
from app.admin.api import (
    auth as admin_auth, overview, users, agent_monitor,
    support, revenue, costs, coupons, system,
)

router = APIRouter()
router.include_router(admin_auth.router, prefix="/auth")
router.include_router(overview.router, prefix="/v1/overview")
router.include_router(users.router, prefix="/v1/users")
router.include_router(agent_monitor.router, prefix="/v1/agent")
router.include_router(support.router, prefix="/v1")
router.include_router(revenue.router, prefix="/v1/revenue")
router.include_router(costs.router, prefix="/v1/costs")
router.include_router(coupons.router, prefix="/v1/coupons")
router.include_router(system.router, prefix="/v1/system")
