import base64
import hashlib
import hmac
import json
import time
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def base64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_jwt_token(payload: Dict[str, Any], secret_key: str, expires_in_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now_ts = int(time.time())
    token_payload = {
        **payload,
        "iat": now_ts,
        "exp": now_ts + expires_in_seconds,
        "iss": settings.OIDC_ISSUER_URL,
        "aud": settings.OIDC_AUDIENCE,
    }
    header_b64 = base64url_encode(json.dumps(header).encode("utf-8"))
    payload_b64 = base64url_encode(json.dumps(token_payload).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_and_verify_jwt(token: str, secret_key: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token structure",
            headers={"WWW-Authenticate": "Bearer"},
        )
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = base64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = json.loads(base64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now_ts = int(time.time())
    if "exp" in payload and payload["exp"] < now_ts:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate audience and issuer if configured
    if settings.OIDC_ENABLED:
        if payload.get("aud") != settings.OIDC_AUDIENCE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if payload.get("iss") != settings.OIDC_ISSUER_URL:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return payload


class UserContext:
    def __init__(self, sub: str, email: str, roles: List[str]):
        self.sub = sub
        self.email = email
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


def extract_roles_from_payload(payload: Dict[str, Any]) -> List[str]:
    roles: List[str] = []
    if "roles" in payload and isinstance(payload["roles"], list):
        roles.extend(payload["roles"])
    if "realm_access" in payload and isinstance(payload["realm_access"], dict):
        realm_roles = payload["realm_access"].get("roles", [])
        if isinstance(realm_roles, list):
            roles.extend(realm_roles)
    # Default to viewer if no specific roles found
    if not roles:
        roles.append("viewer")
    return list(set(roles))


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> UserContext:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_and_verify_jwt(token, settings.JWT_SECRET_KEY)
    sub = payload.get("sub", "anonymous")
    email = payload.get("email", "operator@example.com")
    roles = extract_roles_from_payload(payload)

    return UserContext(sub=sub, email=email, roles=roles)


def require_role(allowed_roles: List[str]):
    async def role_checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not any(user.has_role(r) for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles {allowed_roles}",
            )
        return user

    return role_checker
