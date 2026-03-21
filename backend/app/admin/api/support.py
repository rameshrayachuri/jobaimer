"""Admin support tickets."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.api.auth import require_permission, AdminUser
from app.core.database import get_db

router = APIRouter()

@router.get("/tickets")
async def list_tickets(
    status: str = Query("open"),
    page: int = Query(1, ge=1),
    admin: AdminUser = Depends(require_permission("support.read")),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * 25
    result = await db.execute("""
        SELECT st.id,st.user_id,st.subject,st.status,st.priority,st.created_at,u.email
        FROM support_tickets st LEFT JOIN auth.users u ON u.id=st.user_id
        WHERE ($1='all' OR st.status=$1)
        ORDER BY st.created_at DESC LIMIT 25 OFFSET $2
    """, [status, offset])
    rows = result.fetchall()
    return {"tickets": [{"id":str(r[0]),"user_id":str(r[1]),"subject":r[2],"status":r[3],"priority":r[4],"created_at":r[5],"email":r[6]} for r in rows]}

class UpdateTicket(BaseModel):
    status: str
    note: str | None = None

@router.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id: UUID, body: UpdateTicket, admin: AdminUser = Depends(require_permission("support.update")), db: AsyncSession = Depends(get_db)):
    await db.execute("UPDATE support_tickets SET status=$2,updated_at=NOW() WHERE id=$1", [str(ticket_id),body.status])
    return {"updated": True}
