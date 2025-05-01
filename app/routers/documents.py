from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import os
import mimetypes
from app.service.llama_index import LlamaIndexService
from app.helpers.document_helper import get_document_loader

from tempfile import NamedTemporaryFile
from app.database import get_db
from app.crud.llama_index import store_document, get_document_by_id
from app.crud.documents import process_and_store_document, search_documents
from app.schemas.document import DocumentCreate, DocumentResponse, SearchResponse

UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

llama_service = LlamaIndexService()


router = APIRouter(prefix="/documents", tags=["documents"])


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
    try:
        with NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
        
        return await process_and_store_document(db, file, tmp_path)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/local-chunked", response_model=List[DocumentResponse])
async def upload_local_document_chunked(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_path = Path(UPLOAD_DIR) / file.filename
    content = await file.read()
    with file_path.open("wb") as buffer:
        buffer.write(content)
    try:
        return await process_and_store_document(db, file, file_path)
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


@router.post("/ask")
async def ask_question(
    question: str,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Ask a question about the documents"""
    # First retrieve relevant documents
    results = search_documents(db, question, limit)
    
    # Get answer from LLM
    answer = llama_service.ask_question(
        question=question,
        docs=[r.content for r in results]
    )
    
    return {
        "question": question,
        "answer": answer,
        "sources": results
    }