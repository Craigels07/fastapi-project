from sqlalchemy import Column, Integer, String, JSON
from pgvector.sqlalchemy import Vector
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    doc_metadata = Column(JSON, nullable=True)
