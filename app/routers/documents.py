from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import os
import mimetypes

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredImageLoader,
    CSVLoader,
    UnstructuredExcelLoader
)


from app.database import get_db
from app.crud.llama_index import store_document, search_documents, get_document_by_id, store_document_chunked
from app.schemas.document import DocumentCreate, DocumentResponse, SearchResponse

UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Map file extensions to LangChain document loaders
LOADER_MAPPING = {
    ".txt": TextLoader,
    ".md": TextLoader,
    ".pdf": PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc": Docx2txtLoader,
    ".pptx": UnstructuredPowerPointLoader,
    ".ppt": UnstructuredPowerPointLoader,
    ".jpg": UnstructuredImageLoader,
    ".jpeg": UnstructuredImageLoader,
    ".png": UnstructuredImageLoader,
    ".csv": CSVLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls": UnstructuredExcelLoader
}

router = APIRouter(prefix="/documents", tags=["documents"])

def get_document_loader(file_path: str):
    """Get the appropriate document loader based on file extension"""
    ext = Path(file_path).suffix.lower()
    if ext in LOADER_MAPPING:
        return LOADER_MAPPING[ext]
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: {ext}. Supported types: {', '.join(LOADER_MAPPING.keys())}"
    )

@router.post("/", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a document and create its vector embedding"""
    # Save file
    file_path = Path(UPLOAD_DIR) / file.filename
    content = await file.read()
    
    # Save file
    with file_path.open("wb") as buffer:
        buffer.write(content)
    
    try:
        # Get appropriate document loader
        loader_class = get_document_loader(file_path)
        loader = loader_class(str(file_path))
        
        # Load and process document
        documents = loader.load()
        
        # Combine text from all pages/sections
        text_content = "\n\n".join(doc.page_content for doc in documents)
        
        # Create document with vector embedding
        doc_data = DocumentCreate(
            filename=file.filename,
            content_type=file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream",
            filepath=str(file_path),
            content=text_content,
            doc_metadata={"filename": file.filename}
        )
        
        return store_document(db, doc_data)
        
    except Exception as e:
        # Clean up file if processing fails
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@router.post("/chunked", response_model=List[DocumentResponse])
async def upload_document_chunked(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a document and create vector embeddings for both full document and chunks"""
    # Save file
    file_path = Path(UPLOAD_DIR) / file.filename
    content = await file.read()
    
    with file_path.open("wb") as buffer:
        buffer.write(content)
    
    try:
        # Get appropriate document loader
        loader_class = get_document_loader(file_path)
        loader = loader_class(str(file_path))
        
        # Load and process document
        documents = loader.load()
        text_content = "\n\n".join(doc.page_content for doc in documents)
        
        # Create document with vector embedding
        doc_data = DocumentCreate(
            filename=file.filename,
            content_type=file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream",
            filepath=str(file_path),
            content=text_content,
            doc_metadata={"filename": file.filename}
        )
        
        # Store document and chunks
        return store_document_chunked(db, doc_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=List[SearchResponse])
async def search_docs(query: str, limit: int = 5, db: Session = Depends(get_db)):
    """Search documents using semantic similarity"""
    results = search_documents(db, query, limit)
    
    if not results:
        raise HTTPException(status_code=404, detail="No matching documents found")
    
    return results

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a specific document by ID"""
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
