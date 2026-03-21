"""Email service using Resend API."""
import resend
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY


async def send_verification_email(email: str, name: str, token: str) -> None:
    verify_url = f"https://jobaimer.com/verify-email?token={token}"
    resend.Emails.send({
        "from": settings.FROM_EMAIL,
        "to": email,
        "subject": "Verify your JobAimer email",
        "html": f"""
        <h2>Welcome to JobAimer, {name}!</h2>
        <p>Click the link below to verify your email address:</p>
        <a href="{verify_url}" style="background:#6366F1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;">
            Verify Email
        </a>
        <p>This link expires in 24 hours.</p>
        <p>If you didn't create an account, you can safely ignore this email.</p>
        """,
    })


async def send_password_reset_email(email: str, token: str) -> None:
    reset_url = f"https://jobaimer.com/reset-password?token={token}"
    resend.Emails.send({
        "from": settings.FROM_EMAIL,
        "to": email,
        "subject": "Reset your JobAimer password",
        "html": f"""
        <h2>Password Reset</h2>
        <p>Click below to reset your password. This link expires in 1 hour.</p>
        <a href="{reset_url}" style="background:#6366F1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;">
            Reset Password
        </a>
        <p>If you didn't request a reset, you can safely ignore this email.</p>
        """,
    })


async def send_subscription_welcome_email(email: str, plan_name: str) -> None:
    resend.Emails.send({
        "from": settings.FROM_EMAIL,
        "to": email,
        "subject": f"You're on JobAimer {plan_name} — let's find you a job!",
        "html": f"""
        <h2>🎉 Welcome to JobAimer {plan_name}!</h2>
        <p>Your agent is now active and will start applying to jobs on your behalf within the next few hours.</p>
        <p><a href="https://jobaimer.com">View your dashboard →</a></p>
        """,
    })
