from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime, Text, event
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSON
import uuid
import random
import string
from app.database import Base
from datetime import datetime


def generate_flow_code():
    """Generate a human-readable flow code like FLW-XYZ-123"""
    prefix = "FLW"
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    digits = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


class Flow(Base):
    __tablename__ = "flows"

    STATUS = {
        "DRAFT": "draft",
        "PUBLISHED": "published",
        "ARCHIVED": "archived",
    }

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Flow structure stored as JSON
    nodes = Column(JSON, nullable=False, default=list)
    edges = Column(JSON, nullable=False, default=list)
    
    # Flow status and metadata
    status = Column(String, default=STATUS["DRAFT"], nullable=False)
    is_active = Column(Boolean, default=False)
    
    # Trigger configuration
    trigger_type = Column(String, nullable=True)  # "keyword", "any_message", "schedule"
    trigger_keywords = Column(JSON, nullable=True)  # List of keywords for keyword triggers
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    published_at = Column(DateTime, nullable=True)
    
    # Relationships
    organization = relationship("Organization", backref="flows")

    def __repr__(self):
        return f"Flow(code={self.code}, name={self.name}, status={self.status})"


# Event listener to automatically generate code
@event.listens_for(Flow, "before_insert")
def set_flow_code(mapper, connection, target):
    if not target.code:
        target.code = generate_flow_code()
