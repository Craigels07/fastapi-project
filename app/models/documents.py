from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    content = Column(String, nullable=False)
    embedding = Column(Vector(1536))

    file = relationship("File", back_populates="documents")

