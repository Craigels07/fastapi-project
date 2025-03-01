from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.documents import Document

class File(Base):
    __tablename__="files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    filetype = Column(String)
    filepath = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    documents = relationship("Document", back_populates="file", cascade="all, delete")
