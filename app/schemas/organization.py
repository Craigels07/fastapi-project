from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class OrganizationBase(BaseModel):
    """Base schema for Organization"""

    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    woo_commerce: Optional[bool] = False
    organization_metadata: Optional[Dict[str, Any]] = None


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new Organization"""

    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an Organization"""

    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    woo_commerce: Optional[bool] = None
    organization_metadata: Optional[Dict[str, Any]] = None


class OrganizationInDB(OrganizationBase):
    """Database representation of an Organization"""

    id: UUID
    code: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class OrganizationResponse(OrganizationInDB):
    """Response schema for Organization"""

    pass
