"""Admin authentication — separate from user auth system."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.security import hash_password, verify_password

router = APIRouter()
bearer = HTTPBearer()

ADMIN_ROLES = ["super_admin", "ops_admin", "support", "finance", "read_only"]

ROLE_PERMISSIONS = {
    "super_admin": ["*"],
    "ops_admin": ["users.read","users.suspend","agent.*","support.*","coupons.read","overview.*","system.read"],
    "support": ["support.*","users.read","overview.read"],
    "finance": ["revenue.*","costs.*","coupons.*","billing.*","overview.read"],
    "read_only": ["overview.read","users.read","agent.read","revenue.read","coupons.read"],
}


class AdminUser:
    def __init__(self, admin_id: str, email: str, role: str):
        self.id = admin_id
        self.email = email
        self.role = role

    def can(self, permission: str) -> bool:
        perms = ROLE_PERMISSIONS.get(self.role, [])
        if "*" in perms:
            return True
        domain = permission.split(".")[0]
        return permission in perms or f"{domain}.*" in perms


def create_admin_token(admin_id: str, email: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode(
        {"sub": admin_id, "email": email, "role": role, "exp": exp, "type": "admin"},
        settings.ADMIN_SESSION_SECRET, algorithm="HS256"
    )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> AdminUser:
    try:
        payload = jwt.decode(credentials.credentials, settings.ADMIN_SESSION_SECRET, algorithms=["HS256"])
        if payload.get("type") != "admin":
            raise HTTPException(401, "Invalid admin token")
        return AdminUser(admin_id=payload["sub"], email=payload["email"], role=payload["role"])
    except JWTError:
        raise HTTPException(401, "Invalid or expired admin token")


def require_permission(permission: str):
    async def check(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if not admin.can(permission):
            raise HTTPException(403, f"Requires permission: {permission}")
        return admin
    return check


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    role: str
    email: str


@router.post("/sign-in", response_model=AdminLoginResponse)
async def admin_sign_in(body: AdminLoginRequest):
    """Admin login — checks admin_users table using bcrypt password."""
    import asyncpg
    try:
        conn = await asyncpg.connect(settings.ADMIN_DATABASE_URL or settings.DATABASE_URL)
        try:
            row = await conn.fetchrow(
                "SELECT id, email, password_hash, role, is_active FROM admin_users WHERE email = $1 LIMIT 1",
                body.email
            )
        finally:
            await conn.close()
    except Exception:
        raise HTTPException(503, "Database unavailable")

    if not row or not row["is_active"]:
        raise HTTPException(401, "Invalid admin credentials")

    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Invalid admin credentials")

    token = create_admin_token(str(row["id"]), row["email"], row["role"])
    return AdminLoginResponse(access_token=token, role=row["role"], email=row["email"])


@router.post("/sign-out")
async def admin_sign_out(admin: AdminUser = Depends(get_current_admin)):
    return {"message": "Signed out"}
