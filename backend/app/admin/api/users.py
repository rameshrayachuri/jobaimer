"""Admin users management — list, view, suspend, unsuspend."""
import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.api.auth import get_current_admin, AdminUser, require_permission
from app.core.database import get_db

router = APIRouter()

@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, le=100),
    search: str = Query(""),
    admin: AdminUser = Depends(require_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    search_clause = "AND (u.email ILIKE $3)" if search else ""
    params = [per_page, offset] + ([f"%{search}%"] if search else [])
    result = await db.execute(f"""
        SELECT u.id, u.email, u.created_at, ap.first_name, ap.last_name,
               ap.agent_status, s.plan_id, s.status,
               COUNT(a.id) FILTER (WHERE a.deleted_at IS NULL)
        FROM auth.users u
        LEFT JOIN applicant_profiles ap ON ap.user_id = u.id
        LEFT JOIN subscriptions s ON s.user_id = u.id
        LEFT JOIN applications a ON a.user_id = u.id
        WHERE 1=1 {search_clause}
        GROUP BY u.id,u.email,u.created_at,ap.first_name,ap.last_name,ap.agent_status,s.plan_id,s.status
        ORDER BY u.created_at DESC LIMIT $1 OFFSET $2
    """, params)
    rows = result.fetchall()
    return {"users": [
        {"id":str(r[0]),"email":r[1],"created_at":r[2],
         "name":f"{r[3] or ''} {r[4] or ''}".strip(),"agent_status":r[5],
         "plan_id":r[6],"sub_status":r[7],"total_apps":r[8] or 0}
        for r in rows
    ]}

@router.get("/{user_id}")
async def get_user(user_id: UUID, admin: AdminUser = Depends(require_permission("users.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute("""
        SELECT u.id,u.email,u.created_at,ap.first_name,ap.last_name,ap.agent_status,
               s.plan_id,s.status,s.trial_end,s.current_period_end,
               (SELECT COUNT(*) FROM applications WHERE user_id=u.id AND deleted_at IS NULL)
        FROM auth.users u
        LEFT JOIN applicant_profiles ap ON ap.user_id=u.id
        LEFT JOIN subscriptions s ON s.user_id=u.id
        WHERE u.id=$1
    """, [str(user_id)])
    row = result.fetchone()
    if not row: raise HTTPException(404,"User not found")
    return {"id":str(row[0]),"email":row[1],"created_at":row[2],
            "first_name":row[3],"last_name":row[4],"agent_status":row[5],
            "plan_id":row[6],"sub_status":row[7],"trial_end":row[8],
            "current_period_end":row[9],"total_apps":row[10]}

class SuspendRequest(BaseModel):
    reason: str
    duration_hours: int = 168

@router.post("/{user_id}/suspend")
async def suspend_user(user_id: UUID, body: SuspendRequest, admin: AdminUser = Depends(require_permission("users.suspend")), db: AsyncSession = Depends(get_db)):
    from supabase import create_client
    from app.core.config import settings
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    sb.auth.admin.update_user_by_id(str(user_id), {"ban_duration": f"{body.duration_hours}h"})
    await db.execute("UPDATE applicant_profiles SET agent_status='stopped' WHERE user_id=$1",[str(user_id)])
    await db.execute("INSERT INTO admin_audit_log(admin_email,action,target_type,target_id,payload) VALUES($1,'user.suspend','user',$2,$3)",
                     [admin.email,str(user_id),str({"reason":body.reason})])
    return {"suspended":True}

@router.post("/{user_id}/unsuspend")
async def unsuspend_user(user_id: UUID, admin: AdminUser = Depends(require_permission("users.suspend")), db: AsyncSession = Depends(get_db)):
    from supabase import create_client
    from app.core.config import settings
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    sb.auth.admin.update_user_by_id(str(user_id), {"ban_duration": "none"})
    return {"unsuspended":True}

@router.get("/{user_id}/applications")
async def user_apps(user_id: UUID, admin: AdminUser = Depends(require_permission("users.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute("""
        SELECT a.id,a.status,a.applied_at,a.ats_score,jp.title,jp.company
        FROM applications a LEFT JOIN job_postings jp ON jp.id=a.job_posting_id
        WHERE a.user_id=$1 ORDER BY a.created_at DESC LIMIT 100
    """, [str(user_id)])
    return {"applications":[{"id":str(r[0]),"status":r[1],"applied_at":r[2],"ats_score":r[3],"title":r[4],"company":r[5]} for r in result.fetchall()]}
