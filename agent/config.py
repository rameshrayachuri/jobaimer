"""Agent configuration — mirrors backend settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DB_URL: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Temporal
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "jobaimer-prod"
    TEMPORAL_TASK_QUEUE: str = "jobaimer-jobs"
    TEMPORAL_API_KEY: str = ""

    # Application limits per plan
    PLAN_LIMITS: dict = {
        "free_trial": {"max_apps": 5, "max_portals": 3, "tailor_passes": 1},
        "starter_monthly": {"max_apps": 20, "max_portals": 7, "tailor_passes": 3},
        "starter_annual": {"max_apps": 20, "max_portals": 7, "tailor_passes": 3},
        "pro_monthly": {"max_apps": 50, "max_portals": -1, "tailor_passes": 5},
        "pro_annual": {"max_apps": 50, "max_portals": -1, "tailor_passes": 5},
    }

    # Cycle config
    CYCLE_INTERVAL_HOURS: int = 4
    ATS_MATCH_THRESHOLD: float = 0.65
    MAX_APPLY_PER_CYCLE: int = 10
    RESUME_STORAGE_MONTHS: int = 6


settings = AgentSettings()
