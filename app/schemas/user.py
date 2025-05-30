from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union
from uuid import UUID, uuid4


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
        orm_mode = True
        from_attributes = True


class Organization(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    organization_metadata: Optional[str] = None
    woo_commerce: bool


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    phone_number: Optional[str] = None
    organization_id: UUID
    role: str = "user"  # Default to regular user
    status: str = "active"  # Default to active
    user_metadata: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    organization_id: Optional[UUID] = None
    role: Optional[str] = None
    status: Optional[str] = None
    user_metadata: Optional[str] = None


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
        orm_mode = True
        from_attributes = True
