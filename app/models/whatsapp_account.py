from sqlalchemy import Column, String, ForeignKey, event, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import random
import string
from app.database import Base
from datetime import datetime
import enum


def generate_whatsapp_account_code():
    """Generate a human-readable WhatsApp account code like WAC-XYZ-123"""
    prefix = "WAC"
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    digits = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"




class AccountStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    FAILED = "failed"


class WhatsAppAccount(Base):
    """
    Represents a WhatsApp Business Account connection for an organization.
    Stores Twilio subaccount credentials and Meta WABA information.
    Each organization gets an isolated Twilio subaccount for security and billing.
    Multiple phone numbers can be registered under this account via WhatsAppPhoneNumber.
    """
    __tablename__ = "whatsapp_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    
    # Organization relationship (typically one WhatsApp account per organization)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization")
    
    # Twilio subaccount credentials
    twilio_subaccount_sid = Column(String, nullable=False, unique=True, index=True)
    twilio_auth_token = Column(String, nullable=False)  # Should be encrypted
    
    # WhatsApp Business Account (WABA) information
    waba_id = Column(String, nullable=True, index=True)
    meta_business_portfolio_id = Column(String, nullable=True)
    
    # Status tracking
    status = Column(
        Enum(
            AccountStatus,
            name="accountstatus",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=AccountStatus.PENDING,
        nullable=False,
    )
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to phone numbers (one account can have multiple phone numbers)
    phone_numbers = relationship(
        "WhatsAppPhoneNumber",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"WhatsAppAccount(code={self.code}, org_id={self.organization_id}, status={self.status})"
    
    def get_primary_phone_number(self):
        """Get the primary phone number for this account"""
        return self.phone_numbers.filter_by(is_primary=True).first()
    
    def get_active_phone_numbers(self):
        """Get all active phone numbers for this account"""
        from app.models.whatsapp_phone_number import PhoneNumberStatus
        return self.phone_numbers.filter_by(status=PhoneNumberStatus.ACTIVE).all()






# Event listeners to automatically generate codes
@event.listens_for(WhatsAppAccount, "before_insert")
def set_whatsapp_account_code(mapper, connection, target):
    if not target.code:
        target.code = generate_whatsapp_account_code()


