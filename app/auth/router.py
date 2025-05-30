from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Any, Dict
from pydantic import BaseModel
from datetime import timedelta
from uuid import UUID

from app.database import get_db
from app.auth.utils import authenticate_user
from app.auth.dependencies import create_access_token, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: UUID
    email: str
    role: str
    code: str = None

class TokenData(BaseModel):
    email: str
    role: str

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with user email as the subject
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}, 
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "code": user.code
    }

@router.get("/me", response_model=Dict[str, Any])
async def read_users_me(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """
    Get current user information
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "organization_id": current_user.organization_id
    }

# Additional user management endpoints could go here
