"""Admin agent monitoring — active workflows, cycle stats, error rates."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.api.auth import require_permission, AdminUser
from app.core.database import get_db

router = APIRouter()

@router.get("/stats")
async def agent_stats(admin: AdminUser = Depends(require_permission("agent.read")), db: AsyncSession = Depends(get_db)):
    active = (await db.execute("SELECT COUNT(*) FROM applicant_profiles WHERE agent_status='active'")).fetchone()[0]
    paused = (await db.execute("SELECT COUNT(*) FROM applicant_profiles WHERE agent_status='paused'")).fetchone()[0]
    apps_24h = (await db.execute("SELECT COUNT(*) FROM applications WHERE applied_at>=NOW()-INTERVAL '24 hours'")).fetchone()[0]
    apps_7d = (await db.execute("SELECT COUNT(*) FROM applications WHERE applied_at>=NOW()-INTERVAL '7 days'")).fetchone()[0]
    avg_ats = (await db.execute("SELECT AVG(ats_score) FROM applications WHERE applied_at>=NOW()-INTERVAL '24 hours' AND ats_score IS NOT NULL")).fetchone()[0]
    return {
        "active_agents": active, "paused_agents": paused,
        "apps_last_24h": apps_24h, "apps_last_7d": apps_7d,
        "avg_ats_24h": round(float(avg_ats),1) if avg_ats else 0,
    }

@router.get("/cycles")
async def recent_cycles(admin: AdminUser = Depends(require_permission("agent.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute("""
        SELECT u.email, ap.agent_status, ap.last_cycle_at, ap.next_cycle_at,
               COUNT(a.id) FILTER (WHERE a.applied_at>=NOW()-INTERVAL '24 hours')
        FROM applicant_profiles ap
        JOIN auth.users u ON u.id=ap.user_id
        LEFT JOIN applications a ON a.user_id=ap.user_id
        WHERE ap.agent_status='active'
        GROUP BY u.email,ap.agent_status,ap.last_cycle_at,ap.next_cycle_at
        ORDER BY ap.last_cycle_at DESC NULLS LAST LIMIT 50
    """)
    rows = result.fetchall()
    return {"cycles": [{"email":r[0],"status":r[1],"last_cycle":r[2],"next_cycle":r[3],"apps_24h":r[4] or 0} for r in rows]}
