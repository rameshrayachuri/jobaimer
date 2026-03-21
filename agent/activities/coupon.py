"""Coupon expiry activities — sync expired coupons from Stripe to DB."""
from datetime import datetime, timezone
from temporalio import activity


@activity.defn
async def find_expired_coupons() -> list[str]:
    from agent.db import get_db_pool
    pool = await get_db_pool()
    rows = await pool.fetch("""
        SELECT id::text FROM coupons
        WHERE is_active = true AND is_archived = false
          AND valid_until IS NOT NULL AND valid_until < $1
    """, datetime.now(timezone.utc))
    return [r["id"] for r in rows]


@activity.defn
async def mark_coupon_expired(coupon_id: str) -> None:
    from agent.db import get_db_pool
    pool = await get_db_pool()
    await pool.execute(
        "UPDATE coupons SET is_active = false WHERE id = $1", coupon_id
    )
