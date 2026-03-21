"""SQLAlchemy ORM models for JobAimer — mirrors the Alembic migration schema."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# Subscription Plans
# ─────────────────────────────────────────────
class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    interval: Mapped[str] = mapped_column(String(16))       # month | year
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    max_applications_per_cycle: Mapped[int] = mapped_column(Integer)
    max_portals: Mapped[int] = mapped_column(Integer)       # -1 = unlimited
    ai_tailor_passes: Mapped[int] = mapped_column(Integer, default=0)
    sms_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_price_id: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─────────────────────────────────────────────
# Subscriptions
# ─────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("subscription_plans.id"))
    status: Mapped[str] = mapped_column(String(32))         # trialing|active|past_due|canceled|unpaid
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(128))
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(128))
    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    active_discount: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plan: Mapped[SubscriptionPlan] = relationship("SubscriptionPlan")


# ─────────────────────────────────────────────
# Applicant Profiles
# ─────────────────────────────────────────────
class ApplicantProfile(Base):
    __tablename__ = "applicant_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512))
    github_url: Mapped[Optional[str]] = mapped_column(String(512))
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(512))

    # Job preferences
    job_titles: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    locations: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    remote_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    industries: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    exclude_companies: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(Text))

    # Agent state
    agent_status: Mapped[str] = mapped_column(String(32), default="inactive")
    last_cycle_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_cycle_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_step: Mapped[int] = mapped_column(Integer, default=1)

    # Notifications
    notifications_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_email: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─────────────────────────────────────────────
# Resume Versions
# ─────────────────────────────────────────────
class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_type: Mapped[str] = mapped_column(String(32))   # master | tailored
    original_filename: Mapped[Optional[str]] = mapped_column(String(512))
    s3_key: Mapped[Optional[str]] = mapped_column(String(1024))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    parsed_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_resume_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("resume_versions.id"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Job Portals
# ─────────────────────────────────────────────
class JobPortal(Base):
    __tablename__ = "job_portals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    portal_type: Mapped[str] = mapped_column(String(64))    # linkedin | indeed | greenhouse | lever | workday
    scrape_url: Mapped[str] = mapped_column(String(512))
    apply_url_template: Mapped[Optional[str]] = mapped_column(String(512))
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=10)


# ─────────────────────────────────────────────
# Job Postings
# ─────────────────────────────────────────────
class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("job_portals.id"))
    external_id: Mapped[Optional[str]] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))
    company: Mapped[str] = mapped_column(String(256))
    location: Mapped[Optional[str]] = mapped_column(String(256))
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    apply_url: Mapped[Optional[str]] = mapped_column(String(1024))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Applications
# ─────────────────────────────────────────────
class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        # Partial unique index: only one active application per user+job
        Index(
            "uq_applications_active",
            "user_id", "job_posting_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_posting_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    status: Mapped[str] = mapped_column(String(64), default="discovered")
    portal_name: Mapped[Optional[str]] = mapped_column(String(128))
    application_url: Mapped[Optional[str]] = mapped_column(String(1024))
    tailored_resume_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("resume_versions.id"))
    cover_letter_text: Mapped[Optional[str]] = mapped_column(Text)
    ats_score: Mapped[Optional[float]] = mapped_column(Float)
    matched_keywords: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    missing_keywords: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resume_deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job: Mapped[Optional[JobPosting]] = relationship("JobPosting")
    tailored_resume: Mapped[Optional[ResumeVersion]] = relationship("ResumeVersion", foreign_keys=[tailored_resume_id])


# ─────────────────────────────────────────────
# Coupons & Promo Codes
# ─────────────────────────────────────────────
class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text)
    discount_type: Mapped[str] = mapped_column(String(32))  # percent_off | amount_off
    percent_off: Mapped[Optional[float]] = mapped_column(Float)
    amount_off_cents: Mapped[Optional[int]] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    duration: Mapped[str] = mapped_column(String(32))       # once | repeating | forever
    duration_in_months: Mapped[Optional[int]] = mapped_column(Integer)
    applicable_plans: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    max_redemptions: Mapped[Optional[int]] = mapped_column(Integer)
    redemptions_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    stripe_coupon_id: Mapped[Optional[str]] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    promo_codes: Mapped[list[PromotionCode]] = relationship("PromotionCode", back_populates="coupon")


class PromotionCode(Base):
    __tablename__ = "promotion_codes"
    __table_args__ = (UniqueConstraint("code", name="uq_promo_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coupon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coupons.id"))
    code: Mapped[str] = mapped_column(String(64))
    stripe_promotion_code_id: Mapped[Optional[str]] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_redemptions: Mapped[Optional[int]] = mapped_column(Integer)
    redemptions_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    coupon: Mapped[Coupon] = relationship("Coupon", back_populates="promo_codes")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    coupon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coupons.id"))
    promotion_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("promotion_codes.id"))
    plan_id: Mapped[str] = mapped_column(String(64))
    original_amount_cents: Mapped[int] = mapped_column(Integer)
    discount_amount_cents: Mapped[int] = mapped_column(Integer)
    final_amount_cents: Mapped[int] = mapped_column(Integer)
    stripe_discount_id: Mapped[Optional[str]] = mapped_column(String(128))
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Support Tickets
# ─────────────────────────────────────────────
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")   # open|in_progress|resolved|closed
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─────────────────────────────────────────────
# User Deletion Log
# ─────────────────────────────────────────────
class UserDeletionLog(Base):
    __tablename__ = "user_deletion_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    grace_period_ends: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    restored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deletion_reason: Mapped[Optional[str]] = mapped_column(String(256))
    total_s3_objects_deleted: Mapped[Optional[int]] = mapped_column(Integer)


# ─────────────────────────────────────────────
# Admin Users + Audit Log
# ─────────────────────────────────────────────
class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(256), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    admin_email: Mapped[str] = mapped_column(String(256))
    action: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[Optional[str]] = mapped_column(String(64))
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
