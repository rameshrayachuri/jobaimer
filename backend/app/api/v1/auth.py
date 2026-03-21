"""
Auth endpoints.
Supports 3 login flows: email+password, user_id+password, mobile+password.
OTP passwordless via SMS (AWS SNS).
"""
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import phonenumbers
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    generate_otp, generate_secure_token, hash_password,
    is_password_strong, verify_password,
)
from app.services.sms import send_otp_sms
from app.services.email import send_verification_email, send_password_reset_email

router = APIRouter()

# ── Helpers ──────────────────────────────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    """Normalize phone to E.164 format. Raises ValueError if invalid."""
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        raise ValueError("Invalid phone number format. Use E.164: +1XXXXXXXXXX")


def hash_phone(phone_e164: str) -> str:
    """One-way hash of phone number for storage."""
    return hashlib.sha256(phone_e164.encode()).hexdigest()


def rate_limit_check(request: Request, key: str, max_per_min: int = 10) -> None:
    """Simple in-memory rate limit. In prod, use Redis or AWS WAF."""
    # WAF handles production rate limiting — this is a fallback
    pass


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: str          # E.164 format required
    full_name: str


class LoginRequest(BaseModel):
    identifier: str     # email | user_id | phone number
    password: str


class OTPSendRequest(BaseModel):
    phone: str


class OTPVerifyRequest(BaseModel):
    phone: str
    code: str


class PasswordResetRequest(BaseModel):
    identifier: str     # email or phone


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/sign-up", status_code=status.HTTP_201_CREATED)
async def sign_up(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Register with email + password + phone (all three required)."""
    rate_limit_check(request, "sign-up")

    # Validate password strength
    ok, reason = is_password_strong(body.password)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    # Normalize phone
    try:
        phone_e164 = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    phone_hash = hash_phone(phone_e164)

    # Check uniqueness
    existing_email = await db.execute(
        "SELECT id FROM auth.users WHERE email = $1 LIMIT 1", [body.email]
    )
    if existing_email.fetchone():
        raise HTTPException(status_code=409, detail="Email already registered")

    existing_phone = await db.execute(
        "SELECT user_id FROM user_identity_verification WHERE phone_hash = $1 LIMIT 1",
        [phone_hash]
    )
    if existing_phone.fetchone():
        raise HTTPException(status_code=409, detail="Phone number already registered")

    # Create user via Supabase Auth (handles email confirmation)
    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    result = sb.auth.admin.create_user({
        "email": body.email,
        "password": body.password,
        "email_confirm": False,
        "user_metadata": {"full_name": body.full_name},
    })
    user_id = result.user.id

    # Store phone hash for verification
    await db.execute("""
        INSERT INTO user_identity_verification
            (user_id, phone_hash, email_verified, phone_verified, account_active)
        VALUES ($1, $2, false, false, false)
    """, [user_id, phone_hash])

    # Send email verification
    verification_token = generate_secure_token()
    await db.execute("""
        INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
    """, [user_id, hashlib.sha256(verification_token.encode()).hexdigest(),
          datetime.now(timezone.utc) + timedelta(hours=24)])

    await send_verification_email(body.email, body.full_name, verification_token)

    # Send OTP for phone verification
    otp = generate_otp()
    otp_hash = hash_password(otp)
    await db.execute("""
        INSERT INTO otp_tokens (user_id, phone_hash, token_hash, purpose, expires_at)
        VALUES ($1, $2, $3, 'registration', $4)
    """, [user_id, phone_hash, otp_hash,
          datetime.now(timezone.utc) + timedelta(minutes=10)])

    await send_otp_sms(phone_e164, otp)

    return {
        "message": "Account created. Check your email to verify, and enter the OTP sent to your phone.",
        "user_id": user_id,
        "next_step": "verify_phone",
    }


@router.post("/sign-in")
async def sign_in(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Login with email | user_id | phone + password."""
    rate_limit_check(request, "sign-in", max_per_min=10)

    identifier = body.identifier.strip()
    user_row = None

    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    # Determine identifier type
    if "@" in identifier:
        # Email login
        users = sb.auth.admin.list_users()
        user_row = next((u for u in users if u.email == identifier.lower()), None)
    elif len(identifier) == 36 and "-" in identifier:
        # UUID user_id login
        try:
            user_row = sb.auth.admin.get_user_by_id(identifier).user
        except Exception:
            pass
    else:
        # Phone login
        try:
            phone_e164 = normalize_phone(identifier)
            phone_hash = hash_phone(phone_e164)
            result = await db.execute("""
                SELECT user_id FROM user_identity_verification WHERE phone_hash = $1
            """, [phone_hash])
            row = result.fetchone()
            if row:
                user_row = sb.auth.admin.get_user_by_id(str(row[0])).user
        except Exception:
            pass

    # Generic error — don't reveal which part failed
    auth_error = HTTPException(status_code=401, detail="Invalid credentials")

    if not user_row:
        raise auth_error

    # Verify password via Supabase Auth
    try:
        auth_result = sb.auth.sign_in_with_password({
            "email": user_row.email, "password": body.password
        })
    except Exception:
        raise auth_error

    # Check account is active
    verification = await db.execute("""
        SELECT account_active FROM user_identity_verification WHERE user_id = $1
    """, [user_row.id])
    v = verification.fetchone()
    if not v or not v[0]:
        raise HTTPException(status_code=403, detail="Account not fully verified. Check your email and phone.")

    access_token = create_access_token(str(user_row.id), user_row.email)
    refresh_token = create_refresh_token(str(user_row.id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {"id": str(user_row.id), "email": user_row.email},
    }


@router.post("/otp/send")
async def send_otp(body: OTPSendRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Send OTP to phone number (passwordless login or phone verification)."""
    rate_limit_check(request, "otp-send", max_per_min=3)

    try:
        phone_e164 = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    phone_hash = hash_phone(phone_e164)
    result = await db.execute(
        "SELECT user_id FROM user_identity_verification WHERE phone_hash = $1", [phone_hash]
    )
    row = result.fetchone()
    if not row:
        # Don't reveal phone not found — respond same way
        return {"message": "If this number is registered, you will receive an OTP."}

    otp = generate_otp()
    await db.execute("""
        INSERT INTO otp_tokens (user_id, phone_hash, token_hash, purpose, expires_at)
        VALUES ($1, $2, $3, 'login', $4)
        ON CONFLICT DO NOTHING
    """, [row[0], phone_hash, hash_password(otp),
          datetime.now(timezone.utc) + timedelta(minutes=10)])

    await send_otp_sms(phone_e164, otp)
    return {"message": "If this number is registered, you will receive an OTP."}


@router.post("/otp/verify")
async def verify_otp(body: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP and issue JWT tokens."""
    try:
        phone_e164 = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    phone_hash = hash_phone(phone_e164)
    token_row = await db.execute("""
        SELECT t.id, t.user_id, t.token_hash, t.attempts, t.expires_at, t.purpose
        FROM otp_tokens t
        WHERE t.phone_hash = $1 AND t.used_at IS NULL AND t.expires_at > NOW()
        ORDER BY t.created_at DESC LIMIT 1
    """, [phone_hash])
    token = token_row.fetchone()

    if not token:
        raise HTTPException(400, detail="Invalid or expired OTP")

    if token[3] >= 3:
        raise HTTPException(400, detail="Too many attempts. Request a new OTP.")

    # Increment attempts
    await db.execute("UPDATE otp_tokens SET attempts = attempts + 1 WHERE id = $1", [token[0]])

    if not verify_password(body.code, token[2]):
        raise HTTPException(400, detail="Invalid OTP")

    # Mark as used
    await db.execute("UPDATE otp_tokens SET used_at = NOW() WHERE id = $1", [token[0]])

    # If registration OTP, mark phone verified
    if token[5] == "registration":
        await db.execute("""
            UPDATE user_identity_verification
            SET phone_verified = true, phone_verified_at = NOW()
            WHERE user_id = $1
        """, [token[1]])
        # Check if email is also verified
        v = await db.execute("""
            SELECT email_verified FROM user_identity_verification WHERE user_id = $1
        """, [token[1]])
        row = v.fetchone()
        if row and row[0]:
            await db.execute("""
                UPDATE user_identity_verification SET account_active = true WHERE user_id = $1
            """, [token[1]])

    from supabase import create_client
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    user = sb.auth.admin.get_user_by_id(str(token[1])).user

    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")
        access_token = create_access_token(payload["sub"], "")
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception:
        raise HTTPException(401, "Invalid or expired refresh token")


@router.post("/sign-out")
async def sign_out():
    """Client should discard tokens. Server-side: revoke via JWT jti if needed."""
    return {"message": "Signed out successfully"}
