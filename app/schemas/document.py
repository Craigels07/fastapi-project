from pydantic import BaseModel
from typing import Dict, Any

class DocumentBase(BaseModel):
    content: str
    content_type: str
    filepath: str
    filename: str
    doc_metadata: Dict[str, Any] | None = None

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(BaseModel):
    id: int
    content: str
    content_type: str
    filepath: str
    doc_metadata: Dict[str, Any]

    class Config:
        from_attributes = True

class SearchResponse(BaseModel):
    id: int
    filename: str
    content: str
    similarity: float

    class Config:
        from_attributes = True
