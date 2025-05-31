from typing import Optional, Dict, Any
from pydantic import BaseModel
from uuid import UUID
from app.models.service_credential import ServiceTypeEnum


class ServiceCredentialBase(BaseModel):
    service_type: ServiceTypeEnum
    name: Optional[str] = None
    is_active: bool = True


class ServiceCredentialCreate(ServiceCredentialBase):
    # This will contain the raw API keys and credentials in unencrypted form
    # They will be encrypted before storage
    credentials: Dict[str, Any]
    organization_id: UUID


class ServiceCredentialUpdate(BaseModel):
    service_type: Optional[ServiceTypeEnum] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None


class ServiceCredentialResponse(ServiceCredentialBase):
    id: UUID
    organization_id: UUID
    
    class Config:
        orm_mode = True


# For specific service types, we can create type-specific schemas
class WooCommerceCredentials(BaseModel):
    woo_url: str
    consumer_key: str
    consumer_secret: str


class TakealotCredentials(BaseModel):
    api_key: str
    api_secret: str
    client_id: Optional[str] = None
