"""Billing API — Stripe checkout, billing portal, coupon validation."""
import re
from uuid import UUID
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.core.database import get_db

stripe.api_key = settings.STRIPE_SECRET_KEY
router = APIRouter()


class CheckoutRequest(BaseModel):
    plan_id: str
    promo_code: str | None = None


class CouponValidateRequest(BaseModel):
    code: str
    plan_id: str | None = None


PLAN_PRICE_MAP = {
    "starter_monthly": ("price_starter_monthly", settings.STRIPE_STARTER_MONTHLY_PRICE_ID, 1900),
    "starter_annual": ("price_starter_annual", settings.STRIPE_STARTER_ANNUAL_PRICE_ID, 19000),
    "pro_monthly": ("price_pro_monthly", settings.STRIPE_PRO_MONTHLY_PRICE_ID, 3900),
    "pro_annual": ("price_pro_annual", settings.STRIPE_PRO_ANNUAL_PRICE_ID, 39000),
}


@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session. Optionally pre-apply a promo code."""
    if body.plan_id not in PLAN_PRICE_MAP:
        raise HTTPException(400, "Invalid plan_id")

    _, stripe_price_id, _ = PLAN_PRICE_MAP[body.plan_id]

    # Get or create Stripe customer
    sub_result = await db.execute(
        "SELECT stripe_customer_id FROM subscriptions WHERE user_id = $1 LIMIT 1",
        [str(current_user.id)]
    )
    sub_row = sub_result.fetchone()

    if sub_row:
        customer_id = sub_row[0]
    else:
        profile = await db.execute(
            "SELECT full_name, email FROM applicant_profiles ap JOIN auth.users u ON u.id = ap.user_id WHERE ap.user_id = $1",
            [str(current_user.id)]
        )
        p = profile.fetchone()
        customer = stripe.Customer.create(
            email=current_user.email,
            name=p[0] if p else "",
            metadata={"user_id": str(current_user.id)},
        )
        customer_id = customer.id

    # Resolve promo code
    stripe_promo_id = None
    if body.promo_code:
        code_upper = body.promo_code.upper().strip()
        promo = await db.execute("""
            SELECT pc.stripe_promotion_code_id
            FROM promotion_codes pc
            JOIN coupons c ON c.id = pc.coupon_id
            WHERE pc.code_upper = $1 AND pc.is_active = true
              AND c.is_active = true AND c.is_archived = false
              AND (c.valid_until IS NULL OR c.valid_until > NOW())
            LIMIT 1
        """, [code_upper])
        promo_row = promo.fetchone()
        if promo_row:
            stripe_promo_id = promo_row[0]

    # Is this a new user (no prior subscription)?
    is_new = sub_row is None
    trial_days = 14 if is_new else 0

    session_params = {
        "customer": customer_id,
        "mode": "subscription",
        "line_items": [{"price": stripe_price_id, "quantity": 1}],
        "payment_method_types": ["card", "paypal", "us_bank_account", "cashapp"],
        "subscription_data": {
            "trial_period_days": trial_days,
            "metadata": {"user_id": str(current_user.id), "plan_id": body.plan_id},
        },
        "success_url": f"https://jobaimer.com/?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": "https://jobaimer.com/?billing=canceled",
        "metadata": {"user_id": str(current_user.id), "plan_id": body.plan_id},
    }

    if stripe_promo_id:
        session_params["discounts"] = [{"promotion_code": stripe_promo_id}]
    else:
        session_params["allow_promotion_codes"] = True

    session = stripe.checkout.Session.create(**session_params)
    return {"checkout_url": session.url}


@router.post("/billing/portal")
async def billing_portal(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Open Stripe's hosted billing portal (update card, cancel, download invoices)."""
    result = await db.execute(
        "SELECT stripe_customer_id FROM subscriptions WHERE user_id = $1", [str(current_user.id)]
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(400, "No active subscription found")

    session = stripe.billing_portal.Session.create(
        customer=row[0],
        return_url="https://jobaimer.com/?tab=billing",
    )
    return {"portal_url": session.url}


@router.get("/billing/subscription")
async def get_subscription(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT s.plan_id, s.status, s.current_period_end, s.cancel_at_period_end,
               s.trial_end, sp.display_name, sp.max_apps_per_cycle, sp.max_cycles_per_day,
               sp.max_portals, sp.cover_letter_enabled, sp.sms_alerts_enabled
        FROM subscriptions s
        JOIN subscription_plans sp ON sp.id = s.plan_id
        WHERE s.user_id = $1 LIMIT 1
    """, [str(current_user.id)])
    row = result.fetchone()
    if not row:
        return {"plan_id": None, "status": "inactive"}
    return {
        "plan_id": row[0], "status": row[1],
        "current_period_end": row[2], "cancel_at_period_end": row[3],
        "trial_end": row[4],
        "plan": {
            "name": row[5], "max_apps_per_cycle": row[6],
            "max_cycles_per_day": row[7], "max_portals": row[8],
            "cover_letter_enabled": row[9], "sms_alerts_enabled": row[10],
        },
    }


@router.get("/billing/invoices")
async def list_invoices(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT amount_paid_cents, currency, status, payment_method_type,
               invoice_pdf_url, hosted_invoice_url, period_start, period_end, paid_at
        FROM invoices WHERE user_id = $1 ORDER BY paid_at DESC LIMIT 24
    """, [str(current_user.id)])
    rows = result.fetchall()
    return {"invoices": [
        {
            "amount_paid": r[0] / 100, "currency": r[1], "status": r[2],
            "payment_method": r[3], "pdf_url": r[4],
            "hosted_url": r[5], "period_start": r[6], "paid_at": r[8],
        }
        for r in rows
    ]}


# ── Coupon validation ─────────────────────────────────────────────────────────

@router.post("/billing/coupons/validate")
async def validate_coupon(
    body: CouponValidateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate promo code + return discount preview. Does NOT consume the code."""
    # Format validation first (rule C2) — prevents DB load from garbage
    code_upper = body.code.upper().strip()
    if not re.match(r'^[A-Z0-9\-]{3,20}$', code_upper):
        raise HTTPException(400, "Invalid or expired coupon code")

    promo = await db.execute("""
        SELECT pc.id, pc.stripe_promotion_code_id, pc.max_redemptions,
               pc.redemptions_count, pc.valid_until,
               c.id as coupon_id, c.discount_type, c.percent_off, c.amount_off_cents,
               c.duration, c.duration_in_months, c.applicable_plans,
               c.max_redemptions as c_max, c.redemptions_count as c_count,
               c.valid_until as c_valid_until
        FROM promotion_codes pc
        JOIN coupons c ON c.id = pc.coupon_id
        WHERE pc.code_upper = $1 AND pc.is_active = true
          AND c.is_active = true AND c.is_archived = false
        LIMIT 1
    """, [code_upper])
    p = promo.fetchone()

    generic_error = HTTPException(400, "Invalid or expired coupon code")
    if not p:
        raise generic_error

    now = datetime.now(timezone.utc)
    if p[4] and p[4] < now:   # promo valid_until
        raise generic_error
    if p[14] and p[14] < now:  # coupon valid_until
        raise generic_error

    # Redemption limits
    if p[2] and p[3] >= p[2]:
        raise generic_error
    if p[12] and p[13] >= p[12]:
        raise generic_error

    # Already used by this user?
    existing = await db.execute("""
        SELECT id FROM coupon_redemptions WHERE coupon_id = $1 AND user_id = $2 LIMIT 1
    """, [str(p[5]), str(current_user.id)])
    if existing.fetchone():
        raise HTTPException(400, "You have already used this coupon")

    # Plan restriction
    if body.plan_id and p[11]:
        if body.plan_id not in p[11]:
            raise HTTPException(400, f"Coupon not valid for this plan")

    # Compute discount preview
    original_cents = 1900  # default Starter Monthly
    if body.plan_id and body.plan_id in PLAN_PRICE_MAP:
        original_cents = PLAN_PRICE_MAP[body.plan_id][2]

    if p[6] == "percent_off":
        discount_cents = int(original_cents * float(p[7]) / 100)
    else:
        discount_cents = min(p[8], original_cents)

    final_cents = original_cents - discount_cents

    duration_label = {"once": "one month", "forever": "every month"}.get(
        p[9], f"{p[10]} months"
    )

    return {
        "valid": True,
        "code": code_upper,
        "stripe_promotion_code_id": p[1],
        "discount_type": p[6],
        "percent_off": float(p[7]) if p[7] else None,
        "amount_off_cents": p[8],
        "duration": p[9],
        "duration_in_months": p[10],
        "original_price_cents": original_cents,
        "discounted_price_cents": final_cents,
        "savings_cents": discount_cents,
        "savings_label": f"{int(p[7])}% off for {duration_label}" if p[6] == "percent_off"
                         else f"${discount_cents/100:.2f} off for {duration_label}",
    }
