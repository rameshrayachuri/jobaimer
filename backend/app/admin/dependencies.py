"""Admin authentication dependencies — separate from user auth."""
from enum import Enum
from functools import wraps
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_token

bearer = HTTPBearer()


class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    OPS_ADMIN   = "ops_admin"
    SUPPORT     = "support"
    FINANCE     = "finance"
    READ_ONLY   = "read_only"


class AdminUser:
    def __init__(self, admin_id: str, email: str, role: str):
        self.id    = admin_id
        self.email = email
        self.role  = AdminRole(role)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> AdminUser:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "admin_access":
            raise HTTPException(401, "Invalid admin token")
        return AdminUser(
            admin_id=payload["sub"],
            email=payload.get("email", ""),
            role=payload.get("role", "read_only"),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
        )


def require_roles(*roles: AdminRole):
    """Dependency factory — raises 403 if current admin lacks role."""
    async def check(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in roles:
            raise HTTPException(403, f"Requires role: {[r.value for r in roles]}")
        return admin
    return check
