"""Admin revenue — MRR, ARR, churn, invoice history."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.api.auth import require_permission, AdminUser
from app.core.database import get_db
import stripe
from app.core.config import settings

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

@router.get("/summary")
async def revenue_summary(admin: AdminUser = Depends(require_permission("revenue.read")), db: AsyncSession = Depends(get_db)):
    mrr = (await db.execute("""
        SELECT COALESCE(SUM(sp.amount_cents * CASE sp.interval WHEN 'year' THEN 1.0/12 ELSE 1 END),0)
        FROM subscriptions s JOIN subscription_plans sp ON sp.id=s.plan_id
        WHERE s.status IN ('active','trialing')
    """)).fetchone()[0]
    by_plan = await db.execute("""
        SELECT sp.display_name, sp.id, COUNT(s.id), SUM(sp.amount_cents)
        FROM subscriptions s JOIN subscription_plans sp ON sp.id=s.plan_id
        WHERE s.status='active'
        GROUP BY sp.id,sp.display_name ORDER BY sp.amount_cents DESC
    """)
    trials = (await db.execute("SELECT COUNT(*) FROM subscriptions WHERE status='trialing'")).fetchone()[0]
    canceled_30d = (await db.execute("SELECT COUNT(*) FROM subscriptions WHERE status='canceled' AND canceled_at>=NOW()-INTERVAL '30 days'")).fetchone()[0]
    new_30d = (await db.execute("SELECT COUNT(*) FROM subscriptions WHERE created_at>=NOW()-INTERVAL '30 days'")).fetchone()[0]
    return {
        "mrr_cents": int(mrr or 0),
        "arr_cents": int((mrr or 0) * 12),
        "by_plan": [{"name":r[0],"plan_id":r[1],"count":r[2],"total_cents":r[3]} for r in by_plan.fetchall()],
        "active_trials": trials,
        "canceled_last_30d": canceled_30d,
        "new_subs_last_30d": new_30d,
    }

@router.get("/invoices")
async def recent_invoices(limit: int = Query(50, le=200), admin: AdminUser = Depends(require_permission("revenue.read"))):
    invoices = stripe.Invoice.list(limit=limit, expand=["data.customer"])
    return {"invoices": [
        {"id":inv.id,"customer_email":inv.customer_email,"amount_paid":inv.amount_paid,
         "status":inv.status,"created":inv.created,"period_start":inv.period_start,"period_end":inv.period_end}
        for inv in invoices.auto_paging_iter()
    ][:limit]}

@router.get("/coupon-impact")
async def coupon_impact(admin: AdminUser = Depends(require_permission("revenue.read")), db: AsyncSession = Depends(get_db)):
    result = await db.execute("""
        SELECT c.name, COUNT(cr.id), SUM(cr.discount_amount_cents), SUM(cr.final_amount_cents)
        FROM coupon_redemptions cr JOIN coupons c ON c.id=cr.coupon_id
        WHERE cr.redeemed_at >= NOW()-INTERVAL '90 days'
        GROUP BY c.id,c.name ORDER BY SUM(cr.discount_amount_cents) DESC
    """)
    return {"coupons": [{"name":r[0],"redemptions":r[1],"total_discount_cents":r[2],"total_revenue_cents":r[3]} for r in result.fetchall()]}
