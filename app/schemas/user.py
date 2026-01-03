from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from uuid import UUID


class UserBase(BaseModel):
    name: str
    email: EmailStr


class OrganizationCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    organization_metadata: Optional[str] = None
    woo_commerce: bool = False


class OrganizationRead(OrganizationCreate):
    id: UUID

    class Config:
        from_attributes = True


class Organization(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    organization_metadata: Optional[str] = None
    woo_commerce: bool
    users: Optional[List["UserResponse"]] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    phone_number: Optional[str] = None
    organization_id: UUID
    role: str = "user"  # Default to regular user
    status: str = "active"  # Default to active
    user_metadata: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        """Validate password doesn't exceed bcrypt's 72-byte limit"""
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot exceed 72 bytes when UTF-8 encoded')
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    phone_number: Optional[str] = None
    organization_id: Optional[UUID] = None
    role: Optional[str] = None
    status: Optional[str] = None
    user_metadata: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate password doesn't exceed bcrypt's 72-byte limit"""
        if v is not None and len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot exceed 72 bytes when UTF-8 encoded')
        return v


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    phone_number: Optional[str] = None
    organization_id: UUID
    role: str
    status: str
    user_metadata: Optional[str] = None

    class Config:
        from_attributes = True
