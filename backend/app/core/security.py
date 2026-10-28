import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import jwt
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.repositories.mongo_repository import repository
from app.models.schemas import UserProfile, UserRole

security_bearer = HTTPBearer(auto_error=False)

# In-memory session and revocation cache
SESSION_TOKENS: Dict[str, Dict[str, Any]] = {}
REVOKED_TOKENS: set = set()

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}:{hashed}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify password against stored salt:hash."""
    try:
        salt, hashed = stored_hash.split(":", 1)
        check = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return secrets.compare_digest(check, hashed)
    except Exception:
        return False

def create_access_token(user_id: str, email: str, role: UserRole, employee_id: Optional[str] = None) -> str:
    """
    Generate secure signed JWT access token with expiration.
    Also persists active session to database.
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta
    jti = f"jwt_{uuid.uuid4().hex}"

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "employee_id": employee_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": jti
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    token_data = {
        "token": token,
        "user_id": user_id,
        "email": email,
        "role": role,
        "employee_id": employee_id,
        "created_at": now.isoformat(),
        "expires_at": expire.isoformat(),
        "is_active": True
    }
    SESSION_TOKENS[token] = token_data
    repository.update("user_sessions", {"token": token}, token_data, upsert=True)
    return token

def revoke_token(token: str) -> bool:
    """Revoke/blacklist a session token on logout."""
    REVOKED_TOKENS.add(token)
    if token in SESSION_TOKENS:
        SESSION_TOKENS[token]["is_active"] = False
    now_str = datetime.now(timezone.utc).isoformat()
    repository.update("user_sessions", {"token": token}, {"is_active": False, "revoked_at": now_str})
    repository.insert("revoked_tokens", {"token": token, "revoked_at": now_str})
    return True

def is_token_revoked(token: str) -> bool:
    """Check if token is marked as revoked."""
    if token in REVOKED_TOKENS:
        return True
    revoked_doc = repository.find_one("revoked_tokens", {"token": token})
    if revoked_doc:
        REVOKED_TOKENS.add(token)
        return True
    return False

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> UserProfile:
    """
    Dependency to authenticate request.
    Validates Authorization: Bearer <token>
    Decodes JWT, verifies signature, expiration, and revocation status.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )

    token = credentials.credentials

    # Check revocation
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been terminated or revoked. Please log in again."
        )

    user_id: Optional[str] = None

    # 1. Attempt JWT decoding
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again."
        )
    except jwt.PyJWTError:
        # Fallback to session store for legacy/test tokens
        session = SESSION_TOKENS.get(token) or repository.find_one("user_sessions", {"token": token})
        if session and session.get("is_active", True):
            user_id = session.get("user_id")
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token."
            )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token."
        )

    user_doc = repository.find_one("users", {"user_id": user_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )

    return UserProfile(
        user_id=user_doc["user_id"],
        email=user_doc["email"],
        name=user_doc.get("name", "User"),
        role=user_doc.get("role", "learner"),
        is_employee=user_doc.get("is_employee", False),
        employee_id=user_doc.get("employee_id"),
        department=user_doc.get("department", "Independent Learning"),
        created_at=user_doc.get("created_at")
    )

def verify_user_access(current_user: UserProfile, target_employee_id: str):
    """
    Ensures that a user can only access their own private data.
    Managers and Admins can access team member records.
    """
    if current_user.role in ["manager", "admin"]:
        return
    
    user_identifiers = {
        current_user.user_id,
        current_user.employee_id or "",
        (current_user.employee_id or "").lower(),
        current_user.user_id.lower()
    }
    
    if target_employee_id and target_employee_id not in user_identifiers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot view or modify another user's private learning data."
        )

def require_role(allowed_roles: List[UserRole]):
    """Role-based authorization guard."""
    def role_checker(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{current_user.role}' not authorized. Requires one of {allowed_roles}."
            )
        return current_user
    return role_checker
