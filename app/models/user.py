from sqlalchemy import Column, String, ForeignKey, event
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import random
import string
from app.database import Base


def generate_org_code():
    """Generate a human-readable organization code like ORG-XYZ-123"""
    prefix = "ORG"
    # Generate 3 random uppercase letters
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    # Generate 3 random digits
    digits = ''.join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


def generate_user_code():
    """Generate a human-readable user code like USR-XYZ-123"""
    prefix = "USR"
    # Generate 3 random uppercase letters
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    # Generate 3 random digits
    digits = ''.join(random.choices(string.digits, k=3))
    return f"{prefix}-{letters}-{digits}"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True)
    organization_metadata = Column(String, nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="organization")
    service_credentials = relationship("ServiceCredential", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    organization = relationship("Organization", back_populates="users")
    role = Column(String, default="user")
    status = Column(String, default="active")
    user_metadata = Column(String, nullable=True)

    def __repr__(self):
        return f"User(id={self.id}, code={self.code}, name={self.name}, email={self.email})"


# Event listeners to automatically generate codes
@event.listens_for(Organization, 'before_insert')
def set_org_code(mapper, connection, target):
    if not target.code:
        target.code = generate_org_code()


@event.listens_for(User, 'before_insert')
def set_user_code(mapper, connection, target):
    if not target.code:
        target.code = generate_user_code()
