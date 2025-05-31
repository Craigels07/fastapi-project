from sqlalchemy import Column, String, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from app.database import Base


class ServiceTypeEnum(enum.Enum):
    WOOCOMMERCE = "woocommerce"
    TAKEALOT = "takealot"
    OCTIVE = "octive"
    # Add more service types as needed


class ServiceCredential(Base):
    __tablename__ = "service_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    service_type = Column(Enum(ServiceTypeEnum), nullable=False)
    
    # Credential fields - these will be encrypted at rest
    credentials = Column(JSON, nullable=False)
    
    # Optional metadata
    is_active = Column(String, default=True)
    name = Column(String, nullable=True)  # A friendly name for this credential set
    
    # Relationships
    organization = relationship("Organization", back_populates="service_credentials")
    
    class Config:
        orm_mode = True
