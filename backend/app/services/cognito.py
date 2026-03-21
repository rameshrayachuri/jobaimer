"""AWS Cognito helpers — user pool operations replacing Supabase Auth."""
import hashlib
import hmac
import base64
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


def _cognito_client():
    return boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)


def _secret_hash(username: str) -> str | None:
    """Compute SECRET_HASH for Cognito if client secret is configured."""
    if not settings.COGNITO_CLIENT_SECRET:
        return None
    msg = username + settings.COGNITO_CLIENT_ID
    dig = hmac.new(
        settings.COGNITO_CLIENT_SECRET.encode("utf-8"),
        msg.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()


def _auth_params(username: str, password: str) -> dict:
    params: dict = {"USERNAME": username, "PASSWORD": password}
    secret = _secret_hash(username)
    if secret:
        params["SECRET_HASH"] = secret
    return params


def cognito_sign_up(email: str, password: str, full_name: str) -> str:
    """Create user in Cognito. Returns Cognito sub (user ID)."""
    client = _cognito_client()
    kwargs: dict = {
        "ClientId": settings.COGNITO_CLIENT_ID,
        "Username": email,
        "Password": password,
        "UserAttributes": [
            {"Name": "email", "Value": email},
            {"Name": "name", "Value": full_name},
        ],
    }
    secret = _secret_hash(email)
    if secret:
        kwargs["SecretHash"] = secret

    try:
        result = client.sign_up(**kwargs)
        return result["UserSub"]
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UsernameExistsException":
            raise ValueError("Email already registered")
        if code == "InvalidPasswordException":
            raise ValueError(e.response["Error"]["Message"])
        raise


def cognito_confirm_sign_up(email: str, code: str) -> None:
    """Confirm email with the code Cognito sent."""
    client = _cognito_client()
    kwargs: dict = {
        "ClientId": settings.COGNITO_CLIENT_ID,
        "Username": email,
        "ConfirmationCode": code,
    }
    secret = _secret_hash(email)
    if secret:
        kwargs["SecretHash"] = secret
    try:
        client.confirm_sign_up(**kwargs)
    except ClientError as e:
        raise ValueError(e.response["Error"]["Message"])


def cognito_sign_in(email: str, password: str) -> dict:
    """Authenticate user. Returns {access_token, refresh_token, id_token, sub}."""
    client = _cognito_client()
    kwargs: dict = {
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": settings.COGNITO_CLIENT_ID,
        "AuthParameters": _auth_params(email, password),
    }
    try:
        result = client.initiate_auth(**kwargs)
        tokens = result["AuthenticationResult"]
        # Decode sub from id_token without full JWT validation
        # (we validate our own JWTs; Cognito token is just for identity)
        import json
        id_payload = json.loads(
            base64.b64decode(tokens["IdToken"].split(".")[1] + "==").decode()
        )
        return {
            "sub": id_payload["sub"],
            "email": id_payload.get("email", email),
            "access_token": tokens["AccessToken"],
            "refresh_token": tokens.get("RefreshToken"),
            "id_token": tokens["IdToken"],
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise ValueError("Invalid credentials")
        if code == "UserNotConfirmedException":
            raise ValueError("Email not confirmed. Check your inbox.")
        raise


def cognito_admin_get_user(email: str) -> dict | None:
    """Get user attributes from Cognito by email. Returns None if not found."""
    client = _cognito_client()
    try:
        result = client.admin_get_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
        )
        attrs = {a["Name"]: a["Value"] for a in result["UserAttributes"]}
        return {
            "sub": attrs.get("sub"),
            "email": attrs.get("email", email),
            "name": attrs.get("name", ""),
            "email_verified": attrs.get("email_verified") == "true",
            "status": result["UserStatus"],
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "UserNotFoundException":
            return None
        raise


def cognito_admin_create_user(email: str, full_name: str, temp_password: str) -> str:
    """Admin-create user (auto-confirms email). Returns sub."""
    client = _cognito_client()
    result = client.admin_create_user(
        UserPoolId=settings.COGNITO_USER_POOL_ID,
        Username=email,
        TemporaryPassword=temp_password,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": full_name},
        ],
        MessageAction="SUPPRESS",  # Don't send Cognito welcome email; we send ours
    )
    attrs = {a["Name"]: a["Value"] for a in result["User"]["Attributes"]}
    return attrs["sub"]


def cognito_admin_set_password(email: str, password: str) -> None:
    """Permanently set a user's password (moves out of FORCE_CHANGE_PASSWORD)."""
    client = _cognito_client()
    client.admin_set_user_password(
        UserPoolId=settings.COGNITO_USER_POOL_ID,
        Username=email,
        Password=password,
        Permanent=True,
    )


def cognito_admin_delete_user(email: str) -> None:
    """Hard-delete a user from Cognito (called by HardDeleteWorkflow)."""
    client = _cognito_client()
    try:
        client.admin_delete_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "UserNotFoundException":
            raise


def cognito_forgot_password(email: str) -> None:
    """Trigger Cognito's built-in forgot-password flow (sends code to email)."""
    client = _cognito_client()
    kwargs: dict = {
        "ClientId": settings.COGNITO_CLIENT_ID,
        "Username": email,
    }
    secret = _secret_hash(email)
    if secret:
        kwargs["SecretHash"] = secret
    try:
        client.forgot_password(**kwargs)
    except ClientError:
        pass  # Don't reveal if email exists


def cognito_confirm_forgot_password(email: str, code: str, new_password: str) -> None:
    """Complete the forgot-password flow with the code from email."""
    client = _cognito_client()
    kwargs: dict = {
        "ClientId": settings.COGNITO_CLIENT_ID,
        "Username": email,
        "ConfirmationCode": code,
        "Password": new_password,
    }
    secret = _secret_hash(email)
    if secret:
        kwargs["SecretHash"] = secret
    try:
        client.confirm_forgot_password(**kwargs)
    except ClientError as e:
        raise ValueError(e.response["Error"]["Message"])


def cognito_get_user_by_sub(sub: str) -> dict | None:
    """Look up user by Cognito sub using admin list. Used for phone-based login."""
    client = _cognito_client()
    try:
        result = client.list_users(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Filter=f'sub = "{sub}"',
            Limit=1,
        )
        if not result["Users"]:
            return None
        user = result["Users"][0]
        attrs = {a["Name"]: a["Value"] for a in user["Attributes"]}
        return {"sub": sub, "email": attrs.get("email", ""), "name": attrs.get("name", "")}
    except ClientError:
        return None
