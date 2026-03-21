"""
Auth endpoints — AWS Cognito + Neon Postgres.
Replaces Supabase Auth entirely.
Login flows: email+password, phone+OTP.
Cognito handles email verification & password reset.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import phonenumbers
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    generate_otp, hash_password, is_password_strong, verify_password,
)
from app.services.cognito import (
    cognito_sign_up, cognito_sign_in, cognito_admin_get_user,
    cognito_forgot_password, cognito_confirm_forgot_password,
    cognito_confirm_sign_up, cognito_get_user_by_sub,
)
from app.services.sms import send_otp_sms

router = APIRouter()


def normalize_phone(phone: str) -> str:
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        raise ValueError("Invalid phone number format. Use E.164: +1XXXXXXXXXX")


def hash_phone(phone_e164: str) -> str:
    return hashlib.sha256(phone_e164.encode()).hexdigest()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: str
    full_name: str

class LoginRequest(BaseModel):
    identifier: str   # email or phone
    password: str

class OTPSendRequest(BaseModel):
    phone: str

class OTPVerifyRequest(BaseModel):
    phone: str
    code: str

class ConfirmEmailRequest(BaseModel):
    email: EmailStr
    code: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class RefreshRequest(BaseModel):
    refresh_token: str


# ── Registration ──────────────────────────────────────────────────────────────

@router.post("/sign-up", status_code=status.HTTP_201_CREATED)
async def sign_up(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    ok, reason = is_password_strong(body.password)
    if not ok:
        raise HTTPException(400, detail=reason)

    try:
        phone_e164 = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    phone_hash = hash_phone(phone_e164)

    existing = (await db.execute(
        "SELECT user_id FROM user_identity_verification WHERE phone_hash = $1 LIMIT 1",
        [phone_hash]
    )).fetchone()
    if existing:
        raise HTTPException(409, "Phone number already registered")

    try:
        cognito_sub = cognito_sign_up(body.email, body.password, body.full_name)
    except ValueError as e:
        raise HTTPException(409, detail=str(e))

    # Store in Neon
    await db.execute("""
        INSERT INTO user_identity_verification
            (user_id, phone_hash, email_verified, phone_verified, account_active)
        VALUES ($1, $2, false, false, false)
        ON CONFLICT (user_id) DO NOTHING
    """, [cognito_sub, phone_hash])

    await db.execute("""
        INSERT INTO applicant_profiles (user_id, onboarding_step)
        VALUES ($1, 1) ON CONFLICT (user_id) DO NOTHING
    """, [cognito_sub])

    # Phone OTP
    otp = generate_otp()
    await db.execute("""
        INSERT INTO otp_tokens (user_id, phone_hash, token_hash, purpose, expires_at)
        VALUES ($1, $2, $3, 'registration', $4)
    """, [cognito_sub, phone_hash, hash_password(otp),
          datetime.now(timezone.utc) + timedelta(minutes=10)])
    await send_otp_sms(phone_e164, otp)

    return {
        "message": "Account created. Check your email for a verification code, and enter the OTP sent to your phone.",
        "user_id": cognito_sub,
        "next_step": "verify_email_and_phone",
    }


@router.post("/confirm-email")
async def confirm_email(body: ConfirmEmailRequest, db: AsyncSession = Depends(get_db)):
    """Confirm email with the code Cognito emailed."""
    try:
        cognito_confirm_sign_up(body.email, body.code)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    user = cognito_admin_get_user(body.email)
    if user:
        await db.execute("""
            UPDATE user_identity_verification
            SET email_verified = true, email_verified_at = NOW()
            WHERE user_id = $1
        """, [user["sub"]])
        await db.execute("""
            UPDATE user_identity_verification SET account_active = true
            WHERE user_id = $1 AND phone_verified = true
        """, [user["sub"]])

    return {"message": "Email confirmed."}


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/sign-in")
async def sign_in(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = body.identifier.strip()
    email: str | None = None

    if "@" in identifier:
        email = identifier.lower()
    else:
        try:
            phone_e164 = normalize_phone(identifier)
            phone_hash = hash_phone(phone_e164)
            row = (await db.execute(
                "SELECT user_id FROM user_identity_verification WHERE phone_hash = $1",
                [phone_hash]
            )).fetchone()
            if row:
                info = cognito_get_user_by_sub(str(row[0]))
                email = info["email"] if info else None
        except Exception:
            pass

    auth_error = HTTPException(401, "Invalid credentials")
    if not email:
        raise auth_error

    try:
        result = cognito_sign_in(email, body.password)
    except ValueError as e:
        msg = str(e)
        if "not confirmed" in msg.lower():
            raise HTTPException(403, msg)
        raise auth_error

    user_id = result["sub"]

    v = (await db.execute(
        "SELECT account_active FROM user_identity_verification WHERE user_id = $1", [user_id]
    )).fetchone()
    if not v or not v[0]:
        raise HTTPException(403, "Account not fully verified. Confirm your email and phone first.")

    return {
        "access_token": create_access_token(user_id, email),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {"id": user_id, "email": email},
    }


# ── Phone OTP ─────────────────────────────────────────────────────────────────

@router.post("/otp/send")
async def send_otp(body: OTPSendRequest, db: AsyncSession = Depends(get_db)):
    try:
        phone_e164 = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    phone_hash = hash_phone(phone_e164)
    row = (await db.execute(
        "SELECT user_id FROM user_identity_verification WHERE phone_hash = $1", [phone_hash]
    )).fetchone()

    if row:
        otp = generate_otp()
        await db.execute("""
            INSERT INTO otp_tokens (user_id, phone_hash, token_hash, purpose, expires_at)
            VALUES ($1, $2, $3, 'login', $4)
        """, [row[0], phone_hash, hash_password(otp),
              datetime.now(timezone.utc) + timedelta(minutes=10)])
        await send_otp_sms(phone_e164, otp)

    return {"message": "If this number is registered, you will receive an OTP."}


@router.post("/otp/verify")
async def verify_otp(body: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    try:
        phone_e164 = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    phone_hash = hash_phone(phone_e164)
    token = (await db.execute("""
        SELECT id, user_id, token_hash, attempts, purpose
        FROM otp_tokens
        WHERE phone_hash = $1 AND used_at IS NULL AND expires_at > NOW()
        ORDER BY created_at DESC LIMIT 1
    """, [phone_hash])).fetchone()

    if not token:
        raise HTTPException(400, "Invalid or expired OTP")
    if token[3] >= 3:
        raise HTTPException(400, "Too many attempts. Request a new OTP.")

    await db.execute("UPDATE otp_tokens SET attempts = attempts + 1 WHERE id = $1", [token[0]])

    if not verify_password(body.code, token[2]):
        raise HTTPException(400, "Invalid OTP")

    await db.execute("UPDATE otp_tokens SET used_at = NOW() WHERE id = $1", [token[0]])
    user_id = str(token[1])

    if token[4] == "registration":
        await db.execute("""
            UPDATE user_identity_verification
            SET phone_verified = true, phone_verified_at = NOW() WHERE user_id = $1
        """, [user_id])
        await db.execute("""
            UPDATE user_identity_verification SET account_active = true
            WHERE user_id = $1 AND email_verified = true
        """, [user_id])

    info = cognito_get_user_by_sub(user_id)
    email = info["email"] if info else ""

    return {
        "access_token": create_access_token(user_id, email),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


# ── Password Reset ─────────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    cognito_forgot_password(body.email)
    return {"message": "If this email is registered, you will receive a reset code."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    ok, reason = is_password_strong(body.new_password)
    if not ok:
        raise HTTPException(400, detail=reason)
    try:
        cognito_confirm_forgot_password(body.email, body.code, body.new_password)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"message": "Password reset successfully."}


# ── Refresh + Sign Out ─────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")
        return {
            "access_token": create_access_token(payload["sub"], payload.get("email", "")),
            "token_type": "bearer",
        }
    except Exception:
        raise HTTPException(401, "Invalid or expired refresh token")


@router.post("/sign-out")
async def sign_out():
    return {"message": "Signed out successfully"}
