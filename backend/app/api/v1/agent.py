"""Agent control API — activate, pause, stop, status, dashboard."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import CurrentUser, get_current_user
from app.core.database import get_db

router = APIRouter()

@router.post("/agent/activate")
async def activate_agent(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sub = await db.execute("SELECT status FROM subscriptions WHERE user_id = $1 LIMIT 1", [str(current_user.id)])
    row = sub.fetchone()
    if not row or row[0] not in ("active", "trialing"):
        raise HTTPException(402, "Active subscription required")
    resume = await db.execute("SELECT id FROM resume_versions WHERE user_id = $1 AND version_type='master' AND deleted_at IS NULL LIMIT 1", [str(current_user.id)])
    if not resume.fetchone():
        raise HTTPException(400, "Upload your resume before activating")
    next_cycle = datetime.now(timezone.utc) + timedelta(minutes=2)
    await db.execute("UPDATE applicant_profiles SET agent_status='active', next_cycle_at=$2, updated_at=NOW() WHERE user_id=$1", [str(current_user.id), next_cycle])
    return {"status": "active", "next_cycle_at": next_cycle.isoformat()}

@router.post("/agent/pause")
async def pause_agent(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute("UPDATE applicant_profiles SET agent_status='paused', updated_at=NOW() WHERE user_id=$1", [str(current_user.id)])
    return {"status": "paused"}

@router.post("/agent/stop")
async def stop_agent(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute("UPDATE applicant_profiles SET agent_status='stopped', next_cycle_at=NULL, updated_at=NOW() WHERE user_id=$1", [str(current_user.id)])
    return {"status": "stopped"}

@router.get("/agent/status")
async def agent_status(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute("SELECT agent_status, last_cycle_at, next_cycle_at FROM applicant_profiles WHERE user_id=$1", [str(current_user.id)])
    row = result.fetchone()
    return {"status": row[0], "last_cycle_at": row[1], "next_cycle_at": row[2]} if row else {"status": "inactive"}

@router.get("/dashboard")
async def dashboard(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    s = (await db.execute("""
        SELECT COUNT(*) FILTER (WHERE status NOT IN ('discovered','tailoring_resume','low_match_skipped') AND deleted_at IS NULL),
               COUNT(*) FILTER (WHERE status='interview_scheduled' AND deleted_at IS NULL),
               COUNT(*) FILTER (WHERE status IN ('offer_received','accepted') AND deleted_at IS NULL),
               COUNT(*) FILTER (WHERE status='accepted' AND deleted_at IS NULL),
               COUNT(*) FILTER (WHERE applied_at>=NOW()-INTERVAL '7 days' AND deleted_at IS NULL),
               AVG(ats_score) FILTER (WHERE ats_score IS NOT NULL AND deleted_at IS NULL)
        FROM applications WHERE user_id=$1
    """, [str(current_user.id)])).fetchone()
    a = (await db.execute("SELECT agent_status, next_cycle_at FROM applicant_profiles WHERE user_id=$1", [str(current_user.id)])).fetchone()
    sv = (await db.execute("SELECT s.plan_id,s.status,s.trial_end,s.current_period_end,sp.display_name FROM subscriptions s JOIN subscription_plans sp ON sp.id=s.plan_id WHERE s.user_id=$1 LIMIT 1", [str(current_user.id)])).fetchone()
    recent = (await db.execute("SELECT a.id,a.status,a.applied_at,a.ats_score,jp.title,jp.company FROM applications a LEFT JOIN job_postings jp ON jp.id=a.job_posting_id WHERE a.user_id=$1 AND a.deleted_at IS NULL ORDER BY a.applied_at DESC NULLS LAST LIMIT 10", [str(current_user.id)])).fetchall()
    return {
        "total_applied": s[0] or 0, "interviews_scheduled": s[1] or 0,
        "offers_received": s[2] or 0, "offers_accepted": s[3] or 0,
        "this_week_applied": s[4] or 0, "avg_ats_score": round(float(s[5]),1) if s[5] else 0.0,
        "agent_status": a[0] if a else "inactive", "next_cycle_at": a[1].isoformat() if a and a[1] else None,
        "subscription": {"plan_id":sv[0],"plan_name":sv[4],"status":sv[1],"trial_end":sv[2],"current_period_end":sv[3]} if sv else None,
        "recent_applications": [{"id":str(r[0]),"status":r[1],"applied_at":r[2],"ats_score":r[3],"title":r[4],"company":r[5]} for r in recent],
    }
