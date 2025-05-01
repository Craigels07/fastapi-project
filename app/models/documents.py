from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True) 
    preview = Column(String, nullable=True)  # Optional short text snippet
    content_type = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    doc_metadata = Column(JSON, nullable=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)
    collection = relationship("Collection", back_populates="documents")
    embedding = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"Document(id={self.id}, filename={self.filepath}, preview={self.preview})"
    

class Collection(Base):
    """Collection used to source documents"""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String, nullable=False)
    source_metadata = Column(JSON, nullable=True)
    documents = relationship("Document", back_populates="collection")

    def __repr__(self):
        return f"{self.id} - {self.name}"

    def reset(self, session):
        """
        Delete all document instances of a specific collection and clear the vector store.
        Pass in the SQLAlchemy session.
        """
        # Delete entries in the vector store (pseudo-code, implement as needed)
        # embeddings = OpenAIEmbeddings(api_key=..., model="text-embedding-3-small")
        # vectorstore = PGVector(
        #     embeddings=embeddings, collection_name=self.name, connection=..., use_jsonb=True
        # )
        # vectorstore.delete_collection()

        # Delete instances from the model
        session.query(Document).filter_by(collection_id=self.id).delete()
        session.commit()