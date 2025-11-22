from sqlalchemy import Column, String, ForeignKey, event, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import random
import string
from app.database import Base
from datetime import datetime
import enum


def generate_phone_number_code():
    """Generate a human-readable phone number code like WPN-XYZ-123"""
    prefix = "WPN"
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    digits = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


class PhoneNumberStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    FAILED = "failed"


class WhatsAppPhoneNumber(Base):
    """
    Represents a WhatsApp phone number registered to an organization.
    Multiple phone numbers can exist under one WhatsAppAccount (subaccount).
    This enables organizations to have multiple WhatsApp numbers (e.g., different departments,
    locations, or use cases) all managed under a single Twilio subaccount.
    """
    __tablename__ = "whatsapp_phone_numbers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    
    # Links to WhatsAppAccount (subaccount)
    whatsapp_account_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("whatsapp_accounts.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    account = relationship("WhatsAppAccount", back_populates="phone_numbers")
    
    # Phone number details
    phone_number = Column(String, nullable=False, unique=True, index=True)  # E.164 format
    display_name = Column(String, nullable=True)
    
    # Twilio sender information (each number has its own sender registration)
    sender_sid = Column(String, nullable=True, index=True)  # Twilio Sender SID
    messaging_service_sid = Column(String, nullable=True)
    
    # Webhook URLs (can be different per number for routing flexibility)
    callback_url = Column(String, nullable=True)
    status_callback_url = Column(String, nullable=True)
    
    # Status and flags
    status = Column(Enum(PhoneNumberStatus), default=PhoneNumberStatus.PENDING, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)  # Primary number for organization
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        primary = " (PRIMARY)" if self.is_primary else ""
        return f"WhatsAppPhoneNumber(code={self.code}, phone={self.phone_number}, status={self.status}{primary})"


# Event listeners to automatically generate codes
@event.listens_for(WhatsAppPhoneNumber, "before_insert")
def set_phone_number_code(mapper, connection, target):
    if not target.code:
        target.code = generate_phone_number_code()
