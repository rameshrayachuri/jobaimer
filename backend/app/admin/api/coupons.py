"""Admin coupon management — create, list, deactivate, view redemptions."""
import secrets, string
from datetime import datetime, timezone
from uuid import UUID
import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.api.auth import get_current_admin, AdminUser, require_permission
from app.core.config import settings
from app.core.database import get_db

stripe.api_key = settings.STRIPE_SECRET_KEY
router = APIRouter()


class CreateCouponRequest(BaseModel):
    name: str
    description: str | None = None
    discount_type: str          # percent_off | amount_off
    percent_off: float | None = None
    amount_off_cents: int | None = None
    currency: str = "usd"
    duration: str               # once | repeating | forever
    duration_in_months: int | None = None
    applicable_plans: list[str] | None = None
    max_redemptions: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    promo_codes: list[str] = []


@router.get("")
async def list_coupons(
    admin: AdminUser = Depends(require_permission("coupons.read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT c.id, c.name, c.discount_type, c.percent_off, c.amount_off_cents,
               c.duration, c.duration_in_months, c.max_redemptions, c.redemptions_count,
               c.valid_from, c.valid_until, c.is_active, c.is_archived, c.stripe_coupon_id,
               (SELECT COUNT(*) FROM promotion_codes WHERE coupon_id = c.id) as code_count
        FROM coupons c WHERE c.is_archived = false ORDER BY c.created_at DESC LIMIT 100
    """)
    rows = result.fetchall()
    return {"coupons": [
        {
            "id": str(r[0]), "name": r[1], "discount_type": r[2],
            "percent_off": r[3], "amount_off_cents": r[4],
            "duration": r[5], "duration_in_months": r[6],
            "max_redemptions": r[7], "redemptions_count": r[8],
            "valid_from": r[9], "valid_until": r[10],
            "is_active": r[11], "stripe_coupon_id": r[13],
            "promo_code_count": r[14],
        }
        for r in rows
    ]}


@router.post("")
async def create_coupon(
    body: CreateCouponRequest,
    admin: AdminUser = Depends(require_permission("coupons.create")),
    db: AsyncSession = Depends(get_db),
):
    # Build Stripe coupon
    params: dict = {
        "name": body.name,
        "duration": body.duration,
        "metadata": {"created_by": admin.email},
    }
    if body.discount_type == "percent_off":
        params["percent_off"] = body.percent_off
    else:
        params["amount_off"] = body.amount_off_cents
        params["currency"] = body.currency
    if body.duration == "repeating":
        params["duration_in_months"] = body.duration_in_months
    if body.max_redemptions:
        params["max_redemptions"] = body.max_redemptions
    if body.valid_until:
        params["redeem_by"] = int(body.valid_until.timestamp())

    stripe_coupon = stripe.Coupon.create(**params)

    # Save to DB
    result = await db.execute("""
        INSERT INTO coupons
            (name, description, discount_type, percent_off, amount_off_cents, currency,
             duration, duration_in_months, applicable_plans, max_redemptions,
             valid_from, valid_until, stripe_coupon_id, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                (SELECT id FROM admin_users WHERE email=$14 LIMIT 1))
        RETURNING id
    """, [
        body.name, body.description, body.discount_type, body.percent_off,
        body.amount_off_cents, body.currency, body.duration, body.duration_in_months,
        body.applicable_plans, body.max_redemptions,
        body.valid_from or datetime.now(timezone.utc), body.valid_until,
        stripe_coupon.id, admin.email,
    ])
    coupon_id = result.fetchone()[0]

    # Create promo codes
    codes_created = []
    for code_str in body.promo_codes:
        code_upper = code_str.upper().strip()
        try:
            stripe_promo = stripe.PromotionCode.create(
                coupon=stripe_coupon.id,
                code=code_upper,
                active=True,
            )
            await db.execute("""
                INSERT INTO promotion_codes (coupon_id, code, stripe_promotion_code_id, created_by)
                VALUES ($1, $2, $3, (SELECT id FROM admin_users WHERE email=$4 LIMIT 1))
            """, [str(coupon_id), code_upper, stripe_promo.id, admin.email])
            codes_created.append(code_upper)
        except stripe.StripeError as e:
            pass  # Log and continue — code may already exist

    # Audit log
    await db.execute("""
        INSERT INTO admin_audit_log (admin_id, admin_email, action, target_type, target_id, payload)
        VALUES ((SELECT id FROM admin_users WHERE email=$1 LIMIT 1), $1, 'coupon.create', 'coupon', $2, $3)
    """, [admin.email, str(coupon_id), str({"name": body.name, "codes": codes_created})])

    return {"coupon_id": str(coupon_id), "stripe_coupon_id": stripe_coupon.id,
            "promo_codes_created": codes_created}


@router.post("/{coupon_id}/deactivate")
async def deactivate_coupon(
    coupon_id: UUID,
    admin: AdminUser = Depends(require_permission("coupons.deactivate")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("SELECT stripe_coupon_id FROM coupons WHERE id=$1", [str(coupon_id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Coupon not found")
    try:
        stripe.Coupon.delete(row[0])
    except Exception:
        pass
    await db.execute("UPDATE coupons SET is_active=false, updated_at=NOW() WHERE id=$1", [str(coupon_id)])
    await db.execute("""
        INSERT INTO admin_audit_log (admin_email, action, target_type, target_id)
        VALUES ($1, 'coupon.deactivate', 'coupon', $2)
    """, [admin.email, str(coupon_id)])
    return {"deactivated": True}


@router.post("/{coupon_id}/promo-codes/generate")
async def generate_code(
    coupon_id: UUID,
    admin: AdminUser = Depends(require_permission("coupons.create")),
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate a cryptographically random 8-char promo code."""
    code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    result = await db.execute("SELECT stripe_coupon_id FROM coupons WHERE id=$1 AND is_active=true", [str(coupon_id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Coupon not found or inactive")
    stripe_promo = stripe.PromotionCode.create(coupon=row[0], code=code, active=True)
    await db.execute("""
        INSERT INTO promotion_codes (coupon_id, code, stripe_promotion_code_id, created_by)
        VALUES ($1, $2, $3, (SELECT id FROM admin_users WHERE email=$4 LIMIT 1))
    """, [str(coupon_id), code, stripe_promo.id, admin.email])
    return {"code": code, "stripe_promotion_code_id": stripe_promo.id}


@router.get("/{coupon_id}/redemptions")
async def coupon_redemptions(
    coupon_id: UUID,
    admin: AdminUser = Depends(require_permission("coupons.read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT cr.id, cr.user_id, cr.plan_id, cr.original_amount_cents,
               cr.discount_amount_cents, cr.final_amount_cents, cr.redeemed_at
        FROM coupon_redemptions cr WHERE cr.coupon_id=$1
        ORDER BY cr.redeemed_at DESC LIMIT 100
    """, [str(coupon_id)])
    rows = result.fetchall()
    return {"redemptions": [
        {"id":str(r[0]),"user_id":str(r[1]),"plan_id":r[2],
         "original":r[3],"discount":r[4],"final":r[5],"redeemed_at":r[6]}
        for r in rows
    ]}
