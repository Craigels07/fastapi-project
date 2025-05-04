from pydantic import BaseModel
from typing import Dict, Any, Optional


class DocumentBase(BaseModel):
    content_type: str
    filepath: str
    preview: Optional[str] = None
    doc_metadata: Optional[Dict[str, Any]] = None
    collection_id: int

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(BaseModel):
    id: int
    collection_id: int
    doc_metadata: Optional[Dict[str, Any]] = None
    preview: Optional[str] = None
    class Config:
        from_attributes = True

class SearchResponse(BaseModel):
    id: int
    collection_id: Optional[int] = None
    filename: Optional[str] = None
    preview: Optional[str] = None
    similarity: float

    class Config:
        from_attributes = True
