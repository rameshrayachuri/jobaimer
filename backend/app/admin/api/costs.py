"""Admin costs — AWS, Anthropic, Supabase, Stripe spend tracking."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.api.auth import require_permission, AdminUser
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()

@router.get("/summary")
async def costs_summary(admin: AdminUser = Depends(require_permission("costs.read")), db: AsyncSession = Depends(get_db)):
    """Aggregate cost data from all providers. Actual API calls happen in background jobs."""
    result = await db.execute("""
        SELECT provider, metric_name, metric_value, recorded_at
        FROM daily_cost_metrics
        WHERE recorded_at >= NOW()-INTERVAL '30 days'
        ORDER BY recorded_at DESC
    """)
    rows = result.fetchall()
    by_provider: dict = {}
    for r in rows:
        p = r[0]
        if p not in by_provider:
            by_provider[p] = []
        by_provider[p].append({"metric": r[1], "value": float(r[2]), "recorded_at": r[3]})
    return {"by_provider": by_provider, "days": 30}

@router.get("/per-user")
async def cost_per_user(admin: AdminUser = Depends(require_permission("costs.read")), db: AsyncSession = Depends(get_db)):
    """Estimated per-user cost breakdown."""
    active_users = (await db.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'")).fetchone()[0] or 1
    anthropic_30d = (await db.execute("""
        SELECT COALESCE(SUM(metric_value),0) FROM daily_cost_metrics
        WHERE provider='anthropic' AND metric_name='cost_usd' AND recorded_at>=NOW()-INTERVAL '30 days'
    """)).fetchone()[0]
    return {
        "active_users": active_users,
        "anthropic_30d_usd": float(anthropic_30d),
        "estimated_per_user_usd": round(float(anthropic_30d) / active_users, 2),
    }
