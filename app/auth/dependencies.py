from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from typing import Optional, Union
from uuid import UUID
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "insecure-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a JWT access token with the provided data and expiration
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """
    Validate the JWT token and return the corresponding user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)):
    """
    Check if the authenticated user is active
    """
    if current_user.status != "active":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def check_organization_access(
    org_id: Union[UUID, str], current_user: User = Depends(get_current_user)
):
    """
    Check if the current user has access to the specified organization

    Authorization rules:
    - super_admin users can access any organization
    - org_admin users can access only their organization
    - regular users can only access their own organization
    """
    # Super admin can access any organization
    if current_user.role == "super_admin":
        return True

    # Org admins and regular users can only access their own organization
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this organization",
        )
    return True


def has_role(required_roles: list):
    """
    Dependency for role-based access control

    Usage:
    @router.get("/admin-only", dependencies=[Depends(has_role(["super_admin", "org_admin"]))])
    def admin_endpoint():
        ...

    Roles hierarchy:
    - super_admin: System-wide administrator, can manage all organizations and users
    - org_admin: Organization administrator, can manage users within their organization
    - user: Regular user with basic access to their organization's resources
    """

    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User with role {current_user.role} doesn't have permission to access this resource",
            )
        return current_user

    return role_checker
