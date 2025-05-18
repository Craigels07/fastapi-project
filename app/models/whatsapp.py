from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class WhatsAppUser(Base):
    __tablename__ = "whatsapp_users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    user_metadata = Column(JSON, nullable=True)

    messages = relationship("WhatsAppMessage", back_populates="user")

    def __repr__(self):
        return f"User(phone={self.phone_number})"


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("whatsapp_users.id"))
    user = relationship("WhatsAppUser", back_populates="messages")

    direction = Column(String, nullable=False)  # "inbound" or "outbound"
    content = Column(Text, nullable=False)
    timestamp = Column(String, nullable=False)
    message_metadata = Column(JSON, nullable=True)

    def __repr__(self):
        return f"[{self.direction}] {self.content[:30]}"


class WhatsAppThread(Base):
    __tablename__ = "whatsapp_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("whatsapp_users.id"))
    topic = Column(String, nullable=True)  # auto or human-labeled
    is_active = Column(Integer, default=1)  # active thread flag
    created_at = Column(String)
    updated_at = Column(String)
