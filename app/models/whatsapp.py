from sqlalchemy import (
    Column,
    String,
    JSON,
    ForeignKey,
    Text,
    Boolean,
    DateTime,
    Integer,
    event,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import random
import string
from app.database import Base
from datetime import datetime


def generate_whatsapp_user_code():
    """Generate a human-readable WhatsApp user code like WHA-XYZ-123"""
    prefix = "WHA"
    # Generate 3 random uppercase letters
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    # Generate 3 random digits
    digits = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


class WhatsAppUser(Base):
    __tablename__ = "whatsapp_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)  # End user's phone number
    profile_name = Column(String, nullable=True)  # End user's WhatsApp profile name
    user_metadata = Column(JSON, nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    messages = relationship("WhatsAppMessage", back_populates="user")
    threads = relationship("WhatsAppThread", back_populates="user")

    def __repr__(self):
        return f"WhatsAppUser(code={self.code}, phone={self.phone_number})"


def generate_whatsapp_message_code():
    """Generate a human-readable WhatsApp message code like MSG-XYZ-123"""
    prefix = "MSG"
    # Generate 3 random uppercase letters
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    # Generate 3 random digits
    digits = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    ROLE = {
        "USER": "user",
        "AGENT": "agent",
        "SYSTEM": "system",
    }

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_users.id"))
    user = relationship("WhatsAppUser", back_populates="messages")

    thread_id = Column(
        UUID(as_uuid=True), ForeignKey("whatsapp_threads.id"), nullable=True
    )
    thread = relationship("WhatsAppThread", back_populates="messages")

    direction = Column(String, nullable=False)  # "inbound" or "outbound"
    role = Column(String, nullable=True, default=ROLE["USER"])  # user, agent, etc.
    content = Column(Text, nullable=False)
    timestamp = Column(String, nullable=False)

    message_sid = Column(String, nullable=True)  # from Twilio

    wa_id = Column(String, nullable=True)  # WaId
    sms_status = Column(String, nullable=True)  # SmsStatus
    profile_name = Column(String, nullable=True)  # ProfileName
    message_type = Column(String, nullable=True)  # MessageType
    num_segments = Column(Integer, nullable=True)  # NumSegments
    num_media = Column(Integer, nullable=True)
    media = Column(JSON, nullable=True)  # [{url, type}, ...]

    message_metadata = Column(JSON, nullable=True)  # full webhook payload or NLP tags
    # 🧠 NLP-related fields
    intent = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)
    entities = Column(JSON, nullable=True)

    def __repr__(self):
        return f"WhatsAppMessage(code={self.code}, direction={self.direction}, content={self.content[:30]})"


def generate_whatsapp_thread_code():
    """Generate a human-readable WhatsApp thread code like THR-XYZ-123"""
    prefix = "THR"
    # Generate 3 random uppercase letters
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    # Generate 3 random digits
    digits = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


class WhatsAppThread(Base):
    __tablename__ = "whatsapp_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_users.id"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    topic = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("WhatsAppUser", back_populates="threads")
    messages = relationship("WhatsAppMessage", back_populates="thread")

    def __repr__(self):
        return f"WhatsAppThread(code={self.code}, topic={self.topic})"


# Event listeners to automatically generate codes
@event.listens_for(WhatsAppUser, "before_insert")
def set_whatsapp_user_code(mapper, connection, target):
    if not target.code:
        target.code = generate_whatsapp_user_code()


@event.listens_for(WhatsAppMessage, "before_insert")
def set_whatsapp_message_code(mapper, connection, target):
    if not target.code:
        target.code = generate_whatsapp_message_code()


@event.listens_for(WhatsAppThread, "before_insert")
def set_whatsapp_thread_code(mapper, connection, target):
    if not target.code:
        target.code = generate_whatsapp_thread_code()

    # Already defined __repr__ above
