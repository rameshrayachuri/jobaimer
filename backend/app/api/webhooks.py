"""Stripe webhook handler — processes subscription lifecycle events."""
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

stripe.api_key = settings.STRIPE_SECRET_KEY
router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError:
        raise HTTPException(400, "Invalid Stripe signature")

    # Use a separate DB session — not the FastAPI dependency (webhooks are async)
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        match event["type"]:
            case "checkout.session.completed":
                await _on_checkout_completed(event["data"]["object"], db)
            case "customer.subscription.updated":
                await _on_subscription_updated(event["data"]["object"], db)
            case "customer.subscription.deleted":
                await _on_subscription_deleted(event["data"]["object"], db)
            case "invoice.payment_succeeded":
                await _on_invoice_paid(event["data"]["object"], db)
            case "invoice.payment_failed":
                await _on_invoice_failed(event["data"]["object"], db)
        await db.commit()

    return {"status": "ok"}


async def _on_checkout_completed(session: dict, db: AsyncSession):
    user_id = session.get("metadata", {}).get("user_id")
    plan_id = session.get("metadata", {}).get("plan_id")
    if not user_id:
        return

    stripe_sub_id = session.get("subscription")
    customer_id = session["customer"]

    sub = stripe.Subscription.retrieve(stripe_sub_id) if stripe_sub_id else None

    await db.execute("""
        INSERT INTO subscriptions
            (user_id, plan_id, stripe_customer_id, stripe_subscription_id,
             stripe_price_id, status, trial_end, current_period_start, current_period_end)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (user_id) DO UPDATE SET
            plan_id = EXCLUDED.plan_id,
            stripe_customer_id = EXCLUDED.stripe_customer_id,
            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
            status = EXCLUDED.status,
            trial_end = EXCLUDED.trial_end,
            current_period_start = EXCLUDED.current_period_start,
            current_period_end = EXCLUDED.current_period_end,
            updated_at = NOW()
    """, [
        user_id, plan_id, customer_id,
        stripe_sub_id,
        sub["items"]["data"][0]["price"]["id"] if sub else None,
        sub["status"] if sub else "active",
        datetime.fromtimestamp(sub["trial_end"], tz=timezone.utc) if sub and sub.get("trial_end") else None,
        datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc) if sub else None,
        datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc) if sub else None,
    ])

    # Check for coupon redemption
    total_discount = session.get("total_details", {}).get("amount_discount", 0)
    if total_discount > 0:
        discounts = session.get("total_details", {}).get("breakdown", {}).get("discounts", [])
        if discounts:
            stripe_promo_id = discounts[0].get("discount", {}).get("promotion_code")
            if stripe_promo_id:
                promo = await db.execute("""
                    SELECT pc.id, pc.coupon_id FROM promotion_codes pc
                    WHERE pc.stripe_promotion_code_id = $1 LIMIT 1
                """, [stripe_promo_id])
                promo_row = promo.fetchone()
                if promo_row:
                    await db.execute("""
                        INSERT INTO coupon_redemptions
                            (coupon_id, promotion_code_id, user_id,
                             original_amount_cents, discount_amount_cents, final_amount_cents,
                             stripe_promotion_code_id)
                        VALUES ($1,$2,$3,$4,$5,$6,$7)
                    """, [
                        str(promo_row[1]), str(promo_row[0]), user_id,
                        session.get("amount_subtotal", 0),
                        total_discount,
                        session.get("amount_total", 0),
                        stripe_promo_id,
                    ])
                    await db.execute(
                        "UPDATE coupons SET redemptions_count = redemptions_count + 1 WHERE id = $1",
                        [str(promo_row[1])]
                    )
                    await db.execute(
                        "UPDATE promotion_codes SET redemptions_count = redemptions_count + 1 WHERE id = $1",
                        [str(promo_row[0])]
                    )


async def _on_subscription_updated(sub: dict, db: AsyncSession):
    customer_id = sub["customer"]
    price_id = sub["items"]["data"][0]["price"]["id"]

    plan = await db.execute(
        "SELECT id FROM subscription_plans WHERE stripe_price_id = $1", [price_id]
    )
    plan_row = plan.fetchone()

    await db.execute("""
        UPDATE subscriptions SET
            status = $1, plan_id = $2, stripe_price_id = $3,
            current_period_start = $4, current_period_end = $5,
            cancel_at_period_end = $6, updated_at = NOW()
        WHERE stripe_customer_id = $7
    """, [
        sub["status"],
        plan_row[0] if plan_row else None,
        price_id,
        datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc),
        datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc),
        sub.get("cancel_at_period_end", False),
        customer_id,
    ])

    # Pause agent if subscription is inactive
    if sub["status"] in ("canceled", "unpaid", "past_due"):
        await db.execute("""
            UPDATE applicant_profiles SET agent_status = 'paused'
            WHERE user_id = (SELECT user_id FROM subscriptions WHERE stripe_customer_id = $1)
        """, [customer_id])


async def _on_subscription_deleted(sub: dict, db: AsyncSession):
    await db.execute("""
        UPDATE subscriptions SET status = 'canceled', canceled_at = NOW()
        WHERE stripe_customer_id = $1
    """, [sub["customer"]])
    await db.execute("""
        UPDATE applicant_profiles SET agent_status = 'inactive'
        WHERE user_id = (SELECT user_id FROM subscriptions WHERE stripe_customer_id = $1)
    """, [sub["customer"]])


async def _on_invoice_paid(invoice: dict, db: AsyncSession):
    user_id = await _get_user_id_by_customer(invoice["customer"], db)
    if not user_id:
        return
    await db.execute("""
        INSERT INTO invoices
            (user_id, stripe_invoice_id, amount_paid_cents, currency, status,
             payment_method_type, invoice_pdf_url, hosted_invoice_url, paid_at)
        VALUES ($1,$2,$3,$4,'paid',$5,$6,$7,$8)
        ON CONFLICT (stripe_invoice_id) DO NOTHING
    """, [
        user_id, invoice["id"], invoice["amount_paid"], invoice["currency"],
        invoice.get("payment_settings", {}).get("payment_method_types", [None])[0],
        invoice.get("invoice_pdf"), invoice.get("hosted_invoice_url"),
        datetime.fromtimestamp(
            invoice["status_transitions"].get("paid_at", 0), tz=timezone.utc
        ) if invoice.get("status_transitions", {}).get("paid_at") else None,
    ])


async def _on_invoice_failed(invoice: dict, db: AsyncSession):
    # Stripe will retry — just log it. Notify user via email.
    pass


async def _get_user_id_by_customer(customer_id: str, db: AsyncSession) -> str | None:
    result = await db.execute(
        "SELECT user_id FROM subscriptions WHERE stripe_customer_id = $1 LIMIT 1",
        [customer_id]
    )
    row = result.fetchone()
    return str(row[0]) if row else None
