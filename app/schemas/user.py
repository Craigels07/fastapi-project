from pydantic import BaseModel, EmailStr
from typing import Optional


class UserBase(BaseModel):
    name: str
    email: EmailStr


class OrganizationCreate(BaseModel):
    name: str
    email: str
    phone_number: str
    organization_metadata: str | None = None
    woo_commerce: bool = False


class OrganizationRead(OrganizationCreate):
    id: int

    class Config:
        orm_mode = True


class Organization(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str
    organization_metadata: str | None = None
    woo_commerce: bool


class UserCreate(BaseModel):
    name: str
    email: str
    phone_number: str
    organization_id: int
    role: str
    status: str
    user_metadata: str | None = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True
