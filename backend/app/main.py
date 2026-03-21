"""JobAimer API — FastAPI application with AWS Lambda/Mangum adapter."""
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from mangum import Mangum

from app.core.config import settings
from app.api.v1 import auth, profile, applications, agent, billing
from app.api import health, webhooks
from app.admin.api.router import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.05,
        )
    yield


app = FastAPI(
    title="JobAimer API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(webhooks.router, prefix="/webhooks")
app.include_router(auth.router, prefix="/auth")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(admin_router, prefix="/admin")

# ── AWS Lambda handler ────────────────────────────────────────────────────────
handler = Mangum(app, lifespan="on")
