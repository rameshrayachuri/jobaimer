"""Initial schema — complete JobAimer database.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, TIMESTAMPTZ

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── User identity & verification ────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS user_identity_verification (
        user_id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
        email_verified      BOOLEAN DEFAULT false,
        email_verified_at   TIMESTAMPTZ,
        phone_verified      BOOLEAN DEFAULT false,
        phone_verified_at   TIMESTAMPTZ,
        phone_hash          TEXT,
        mfa_enabled         BOOLEAN DEFAULT false,
        mfa_method          TEXT,
        account_active      BOOLEAN DEFAULT false,
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        updated_at          TIMESTAMPTZ DEFAULT NOW()
    )""")

    op.execute("""
    CREATE TABLE IF NOT EXISTS otp_tokens (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
        phone_hash  TEXT,
        token_hash  TEXT NOT NULL,
        purpose     TEXT NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL,
        used_at     TIMESTAMPTZ,
        attempts    INTEGER DEFAULT 0,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )""")

    op.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        token_hash  TEXT NOT NULL UNIQUE,
        expires_at  TIMESTAMPTZ NOT NULL,
        used_at     TIMESTAMPTZ,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )""")

    op.execute("""
    CREATE TABLE IF NOT EXISTS login_attempts (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
        identifier      TEXT NOT NULL,
        ip_address      INET,
        attempt_type    TEXT NOT NULL,
        success         BOOLEAN NOT NULL,
        failure_reason  TEXT,
        attempted_at    TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_user ON login_attempts(user_id, attempted_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, attempted_at DESC)")

    # ── Subscription plans ───────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS subscription_plans (
        id                   TEXT PRIMARY KEY,
        display_name         TEXT NOT NULL,
        stripe_price_id      TEXT NOT NULL UNIQUE,
        stripe_product_id    TEXT NOT NULL,
        interval             TEXT NOT NULL,
        amount_cents         INTEGER NOT NULL,
        currency             TEXT DEFAULT 'usd',
        max_apps_per_cycle   INTEGER NOT NULL,
        max_cycles_per_day   INTEGER NOT NULL,
        max_portals          INTEGER NOT NULL,
        claude_tailor_passes INTEGER NOT NULL DEFAULT 3,
        cover_letter_enabled BOOLEAN DEFAULT false,
        sms_alerts_enabled   BOOLEAN DEFAULT false,
        priority_queue       BOOLEAN DEFAULT false,
        is_active            BOOLEAN DEFAULT true,
        created_at           TIMESTAMPTZ DEFAULT NOW()
    )""")

    op.execute("""
    INSERT INTO subscription_plans VALUES
        ('free_trial','Free Trial','price_free','prod_free','trial',0,'usd',5,1,3,3,false,false,false,true,NOW()),
        ('starter_monthly','Starter','price_starter_monthly','prod_starter','month',1900,'usd',20,6,7,3,true,false,false,true,NOW()),
        ('starter_annual','Starter Annual','price_starter_annual','prod_starter','year',19000,'usd',20,6,7,3,true,false,false,true,NOW()),
        ('pro_monthly','Pro','price_pro_monthly','prod_pro','month',3900,'usd',50,6,99,5,true,true,true,true,NOW()),
        ('pro_annual','Pro Annual','price_pro_annual','prod_pro','year',39000,'usd',50,6,99,5,true,true,true,true,NOW())
    ON CONFLICT (id) DO NOTHING
    """)

    # ── Subscriptions ────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id                UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
        plan_id                TEXT NOT NULL REFERENCES subscription_plans(id),
        stripe_customer_id     TEXT NOT NULL UNIQUE,
        stripe_subscription_id TEXT UNIQUE,
        stripe_price_id        TEXT NOT NULL,
        status                 TEXT NOT NULL DEFAULT 'trialing',
        trial_start            TIMESTAMPTZ DEFAULT NOW(),
        trial_end              TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '14 days'),
        current_period_start   TIMESTAMPTZ,
        current_period_end     TIMESTAMPTZ,
        cancel_at_period_end   BOOLEAN DEFAULT false,
        canceled_at            TIMESTAMPTZ,
        created_at             TIMESTAMPTZ DEFAULT NOW(),
        updated_at             TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sub_stripe_customer ON subscriptions(stripe_customer_id)")
    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY IF NOT EXISTS users_own_subscription ON subscriptions
        FOR SELECT USING (user_id = auth.uid())""")

    # ── Invoices ─────────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id                  UUID NOT NULL REFERENCES auth.users(id),
        subscription_id          UUID REFERENCES subscriptions(id),
        stripe_invoice_id        TEXT NOT NULL UNIQUE,
        stripe_payment_intent_id TEXT,
        amount_paid_cents        INTEGER NOT NULL,
        currency                 TEXT DEFAULT 'usd',
        status                   TEXT NOT NULL,
        payment_method_type      TEXT,
        invoice_pdf_url          TEXT,
        hosted_invoice_url       TEXT,
        period_start             TIMESTAMPTZ,
        period_end               TIMESTAMPTZ,
        paid_at                  TIMESTAMPTZ,
        created_at               TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY IF NOT EXISTS users_own_invoices ON invoices FOR SELECT USING (user_id = auth.uid())")

    # ── Applicant profiles ───────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS applicant_profiles (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id             UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
        full_name           TEXT,
        email               TEXT,
        phone               TEXT,
        location            TEXT,
        linkedin_url        TEXT,
        github_url          TEXT,
        portfolio_url       TEXT,
        summary             TEXT,
        total_yoe           DECIMAL(4,1),
        seniority_level     TEXT,
        technical_skills    TEXT[],
        tools               TEXT[],
        target_titles       TEXT[],
        preferred_locations TEXT[],
        remote_preference   TEXT DEFAULT 'any',
        target_industries   TEXT[],
        salary_min          INTEGER,
        salary_max          INTEGER,
        excluded_companies  TEXT[],
        agent_status        TEXT DEFAULT 'inactive',
        last_cycle_at       TIMESTAMPTZ,
        next_cycle_at       TIMESTAMPTZ,
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        updated_at          TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_profiles_agent_status ON applicant_profiles(agent_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_profiles_next_cycle ON applicant_profiles(next_cycle_at) WHERE agent_status = 'active'")
    op.execute("ALTER TABLE applicant_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY IF NOT EXISTS users_own_profile ON applicant_profiles FOR ALL USING (user_id = auth.uid())")

    # ── Resume versions ───────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS resume_versions (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        version_type     TEXT NOT NULL,
        job_posting_id   UUID,
        version_label    TEXT,
        s3_bucket        TEXT NOT NULL DEFAULT 'jobaimer-resumes-prod',
        s3_key           TEXT,
        file_name        TEXT NOT NULL,
        file_size_bytes  INTEGER,
        parsed_data      JSONB NOT NULL DEFAULT '{}',
        ats_score        INTEGER,
        ats_reasoning    TEXT,
        keywords_matched TEXT[],
        keywords_missing TEXT[],
        last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
        deleted_at       TIMESTAMPTZ,
        deletion_reason  TEXT,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_resume_versions_user ON resume_versions(user_id, version_type)")
    op.execute("""CREATE INDEX IF NOT EXISTS idx_resume_versions_cleanup
        ON resume_versions(version_type, last_accessed_at, deleted_at)
        WHERE version_type = 'tailored' AND deleted_at IS NULL""")
    op.execute("ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY IF NOT EXISTS users_own_resumes ON resume_versions FOR ALL USING (user_id = auth.uid())")

    # ── Job postings ──────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS job_postings (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        portal          TEXT NOT NULL,
        portal_job_id   TEXT NOT NULL,
        title           TEXT NOT NULL,
        company         TEXT NOT NULL,
        location        TEXT,
        remote_type     TEXT DEFAULT 'unknown',
        seniority       TEXT,
        job_description TEXT NOT NULL,
        apply_url       TEXT NOT NULL,
        salary_min      INTEGER,
        salary_max      INTEGER,
        salary_currency TEXT DEFAULT 'USD',
        posted_at       TIMESTAMPTZ,
        scraped_at      TIMESTAMPTZ DEFAULT NOW(),
        expires_at      TIMESTAMPTZ,
        UNIQUE(portal, portal_job_id)
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_postings_posted_at ON job_postings(posted_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_postings_jd_fts ON job_postings USING GIN(to_tsvector('english', job_description))")

    # ── Applications ──────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        job_posting_id    UUID NOT NULL REFERENCES job_postings(id),
        resume_version_id UUID REFERENCES resume_versions(id),
        status            TEXT NOT NULL DEFAULT 'discovered',
        failure_reason    TEXT,
        manual_apply_url  TEXT,
        discovered_at     TIMESTAMPTZ DEFAULT NOW(),
        tailored_at       TIMESTAMPTZ,
        applied_at        TIMESTAMPTZ,
        interview_at      TIMESTAMPTZ,
        offer_received_at TIMESTAMPTZ,
        outcome_at        TIMESTAMPTZ,
        confirmation_id   TEXT,
        screenshot_path   TEXT,
        quick_score       DECIMAL(5,2),
        ats_score         INTEGER,
        user_notes        TEXT,
        deleted_at        TIMESTAMPTZ,
        deleted_by        TEXT,
        created_at        TIMESTAMPTZ DEFAULT NOW(),
        updated_at        TIMESTAMPTZ DEFAULT NOW()
    )""")
    # Partial unique index — allows re-apply after user deletes (rule D4)
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_user_active_job
        ON applications(user_id, job_posting_id) WHERE deleted_at IS NULL""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_applications_user_active ON applications(user_id, applied_at DESC) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(user_id, status) WHERE deleted_at IS NULL")
    op.execute("ALTER TABLE applications ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY IF NOT EXISTS users_own_applications ON applications FOR ALL USING (user_id = auth.uid() AND deleted_at IS NULL)")

    # ── Agent cycles ──────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_cycles (
        id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id              UUID NOT NULL REFERENCES auth.users(id),
        started_at           TIMESTAMPTZ DEFAULT NOW(),
        completed_at         TIMESTAMPTZ,
        status               TEXT,
        jobs_discovered      INTEGER DEFAULT 0,
        jobs_tailored        INTEGER DEFAULT 0,
        jobs_applied         INTEGER DEFAULT 0,
        jobs_failed          INTEGER DEFAULT 0,
        jobs_skipped         INTEGER DEFAULT 0,
        claude_api_calls     INTEGER DEFAULT 0,
        claude_tokens_used   INTEGER DEFAULT 0,
        temporal_workflow_id TEXT,
        error_message        TEXT
    )""")

    # ── Storage logs ──────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS resume_download_log (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id           UUID NOT NULL REFERENCES auth.users(id),
        resume_version_id UUID NOT NULL,
        application_id    UUID,
        ip_address        INET,
        downloaded_at     TIMESTAMPTZ DEFAULT NOW()
    )""")

    op.execute("""
    CREATE TABLE IF NOT EXISTS storage_cleanup_log (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        resume_version_id  UUID NOT NULL,
        user_id            UUID NOT NULL,
        s3_key             TEXT,
        reason             TEXT NOT NULL,
        bytes_freed        BIGINT,
        deleted_at         TIMESTAMPTZ DEFAULT NOW(),
        triggered_by_admin UUID
    )""")

    op.execute("""
    CREATE TABLE IF NOT EXISTS user_deletion_log (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id           UUID NOT NULL,
        resource_type     TEXT NOT NULL,
        resource_id       UUID,
        resource_snapshot JSONB,
        s3_key_deleted    TEXT,
        bytes_freed       BIGINT,
        ip_address        INET,
        deleted_at        TIMESTAMPTZ DEFAULT NOW()
    )""")

    # ── Coupons ───────────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name               TEXT NOT NULL,
        description        TEXT,
        discount_type      TEXT NOT NULL CHECK (discount_type IN ('percent_off','amount_off')),
        percent_off        DECIMAL(5,2),
        amount_off_cents   INTEGER,
        currency           TEXT DEFAULT 'usd',
        duration           TEXT NOT NULL CHECK (duration IN ('once','repeating','forever')),
        duration_in_months INTEGER,
        applicable_plans   TEXT[],
        max_redemptions    INTEGER,
        redemptions_count  INTEGER DEFAULT 0,
        valid_from         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        valid_until        TIMESTAMPTZ,
        is_active          BOOLEAN DEFAULT true,
        is_archived        BOOLEAN DEFAULT false,
        stripe_coupon_id   TEXT UNIQUE,
        created_by         UUID,
        updated_by         UUID,
        created_at         TIMESTAMPTZ DEFAULT NOW(),
        updated_at         TIMESTAMPTZ DEFAULT NOW()
    )""")

    op.execute("""
    CREATE TABLE IF NOT EXISTS promotion_codes (
        id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        coupon_id                UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
        code                     TEXT NOT NULL,
        code_upper               TEXT GENERATED ALWAYS AS (UPPER(code)) STORED,
        max_redemptions          INTEGER,
        redemptions_count        INTEGER DEFAULT 0,
        restricted_to_user_id    UUID REFERENCES auth.users(id),
        valid_from               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        valid_until              TIMESTAMPTZ,
        is_active                BOOLEAN DEFAULT true,
        stripe_promotion_code_id TEXT UNIQUE,
        created_by               UUID,
        created_at               TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(code_upper)
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promotion_codes(code_upper) WHERE is_active = true")

    op.execute("""
    CREATE TABLE IF NOT EXISTS coupon_redemptions (
        id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        coupon_id                UUID NOT NULL REFERENCES coupons(id),
        promotion_code_id        UUID NOT NULL REFERENCES promotion_codes(id),
        user_id                  UUID NOT NULL REFERENCES auth.users(id),
        subscription_id          UUID REFERENCES subscriptions(id),
        plan_id                  TEXT REFERENCES subscription_plans(id),
        original_amount_cents    INTEGER NOT NULL,
        discount_amount_cents    INTEGER NOT NULL,
        final_amount_cents       INTEGER NOT NULL,
        stripe_coupon_id         TEXT,
        stripe_promotion_code_id TEXT,
        stripe_invoice_id        TEXT,
        redeemed_at              TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("ALTER TABLE coupon_redemptions ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY IF NOT EXISTS users_own_redemptions ON coupon_redemptions FOR SELECT USING (user_id = auth.uid())")


def downgrade() -> None:
    tables = [
        "coupon_redemptions", "promotion_codes", "coupons",
        "user_deletion_log", "storage_cleanup_log", "resume_download_log",
        "agent_cycles", "applications", "job_postings",
        "resume_versions", "applicant_profiles",
        "invoices", "subscriptions", "subscription_plans",
        "login_attempts", "password_reset_tokens", "otp_tokens",
        "user_identity_verification",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
