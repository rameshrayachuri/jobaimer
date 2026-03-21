from functools import lru_cache
from typing import Literal
from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    # AWS
    AWS_REGION: str = "us-east-1"
    S3_RESUME_BUCKET: str = "jobaimer-resumes-dev"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DB_URL: str = ""

    # Admin Supabase
    ADMIN_SUPABASE_URL: str = ""
    ADMIN_SUPABASE_SERVICE_ROLE_KEY: str = ""
    ADMIN_SUPABASE_DB_URL: str = ""

    # JWT
    API_SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MAX_TOKENS: int = 8000

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_STARTER_MONTHLY_PRICE_ID: str = ""
    STRIPE_STARTER_ANNUAL_PRICE_ID: str = ""
    STRIPE_PRO_MONTHLY_PRICE_ID: str = ""
    STRIPE_PRO_ANNUAL_PRICE_ID: str = ""

    # Agent
    MAX_JOBS_PER_CYCLE: int = 20
    MAX_JOBS_PER_DAY: int = 50
    APPLY_CYCLE_HOURS: int = 4
    MIN_ATS_SCORE: int = 70
    BROWSER_HEADLESS: bool = True

    # Email
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@jobaimer.com"

    # Admin
    ADMIN_SESSION_SECRET: str = "dev-admin-secret"
    ADMIN_IP_ALLOWLIST: str = "127.0.0.1/32"

    # Observability
    SENTRY_DSN: str = ""

    # CORS computed from environment
    ALLOWED_ORIGINS_STR: str = "http://localhost:5173,http://localhost:5174"

    @computed_field  # type: ignore[misc]
    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        if self.ENVIRONMENT == "production":
            return ["https://jobaimer.com", "https://www.jobaimer.com",
                    "https://admin.jobaimer.com"]
        return [o.strip() for o in self.ALLOWED_ORIGINS_STR.split(",")]

    @model_validator(mode="after")
    def check_prod_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            for key in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                        "ANTHROPIC_API_KEY", "STRIPE_SECRET_KEY"]:
                if not getattr(self, key):
                    raise ValueError(f"Missing production secret: {key}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
