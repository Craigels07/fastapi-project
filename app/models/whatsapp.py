from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    ForeignKey,
    Text,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class WhatsAppUser(Base):
    __tablename__ = "whatsapp_users"

    id = Column(Integer, primary_key=True, index=True)
    account_sid = Column(String, nullable=True)
    phone_number = Column(String, unique=True, nullable=False)
    profile_name = Column(String, nullable=True)
    user_metadata = Column(JSON, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))

    messages = relationship("WhatsAppMessage", back_populates="user")
    threads = relationship("WhatsAppThread", back_populates="user")

    def __repr__(self):
        return f"User(phone={self.phone_number})"


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("whatsapp_users.id"))
    user = relationship("WhatsAppUser", back_populates="messages")

    thread_id = Column(Integer, ForeignKey("whatsapp_threads.id"), nullable=True)
    thread = relationship("WhatsAppThread", back_populates="messages")

    direction = Column(String, nullable=False)  # "inbound" or "outbound"
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
        return f"[{self.direction}] {self.content[:30]}"


class WhatsAppThread(Base):
    __tablename__ = "whatsapp_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("whatsapp_users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    topic = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("WhatsAppUser", back_populates="threads")
    messages = relationship("WhatsAppMessage", back_populates="thread")

    def __repr__(self):
        return f"Thread(user={self.user_id}, topic={self.topic})"
