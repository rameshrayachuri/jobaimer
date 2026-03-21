"""Admin overview endpoint."""
from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.admin.api.auth import get_current_admin, AdminUser
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("/kpis")
async def kpis(admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    users = (await db.execute("SELECT COUNT(*) FROM auth.users")).fetchone()[0]
    active = (await db.execute("SELECT COUNT(*) FROM applicant_profiles WHERE agent_status='active'")).fetchone()[0]
    apps_24h = (await db.execute("SELECT COUNT(*) FROM applications WHERE applied_at>=NOW()-INTERVAL '24 hours'")).fetchone()[0]
    mrr = (await db.execute("SELECT COALESCE(SUM(sp.amount_cents),0) FROM subscriptions s JOIN subscription_plans sp ON sp.id=s.plan_id WHERE s.status IN ('active','trialing')")).fetchone()[0]
    avg_ats = (await db.execute("SELECT AVG(ats_score) FROM applications WHERE applied_at>=NOW()-INTERVAL '24 hours'")).fetchone()[0]
    tickets = (await db.execute("SELECT COUNT(*) FROM support_tickets WHERE status='open'")).fetchone()[0]
    return {
        "total_users": users, "active_today": active,
        "apps_last_24h": apps_24h, "mrr_cents": mrr,
        "avg_ats": round(float(avg_ats),1) if avg_ats else 0,
        "open_tickets": tickets,
    }

@router.get("/status")
async def system_status(admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    try:
        await db.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "database": "healthy" if db_ok else "degraded",
        "api": "healthy",
    }
