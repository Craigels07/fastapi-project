from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    organization_metadata = Column(String)
    woo_commerce = Column(Boolean)
    users = relationship("User", order_by="User.id", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    organization = relationship("Organization", back_populates="users")
    role = Column(String)
    status = Column(String)
    user_metadata = Column(String)

    def __repr__(self):
        return f"User(id={self.id}, name={self.name}, email={self.email})"
