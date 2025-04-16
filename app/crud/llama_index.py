from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.documents import Document
from app.schemas.document import DocumentCreate, DocumentResponse, SearchResponse
from app.service.llama_index import LlamaIndexService

llama_service = LlamaIndexService()

def store_document(db: Session, doc_data: DocumentCreate) -> DocumentResponse:
    """Store a document and its vector embedding"""
    # Generate embedding for the document content
    embedding = llama_service.get_embedding(doc_data.content)
    # Pass the embedding list directly - SQLAlchemy will handle the conversion
    
    # Create document record
    print(doc_data)
    doc = Document(
        content_type=doc_data.content_type,
        filepath=doc_data.filepath,
        content=doc_data.content,
        embedding=embedding,
        doc_metadata={"filename": doc_data.filename}
    )
    
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    return DocumentResponse.from_orm(doc)

def store_document_chunked(db: Session, doc_data: DocumentCreate) -> List[DocumentResponse]:
    """Store a document split into chunks with vector embeddings"""
    # Store the full document first
    full_doc = store_document(db, doc_data)
    
    # Now handle chunks
    chunks = llama_service.chunk_text(doc_data.content)
    chunk_docs = []
    
    for i, chunk in enumerate(chunks):
        embedding = llama_service.get_embedding(chunk)
        doc = Document(
            content=chunk,
            content_type=doc_data.content_type,
            filepath=f"{doc_data.filepath}_chunk_{i}",
            embedding=embedding,
            doc_metadata={
                "filename": doc_data.filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "parent_id": full_doc.id
            }
        )
        chunk_docs.append(doc)
    
    db.add_all(chunk_docs)
    db.commit()
    
    return [DocumentResponse.from_orm(doc) for doc in [full_doc] + chunk_docs]

def get_document_by_id(db: Session, document_id: int) -> Optional[DocumentResponse]:
    """Retrieve a document by its ID"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc:
        return DocumentResponse.from_orm(doc)
    return None

def search_documents(db: Session, query: str, limit: int = 5) -> List[SearchResponse]:
    """Search documents using semantic similarity"""
    query_embedding = llama_service.get_embedding(query)
    
    sql = text("""
        SELECT d.id, d.doc_metadata->>'filename' as filename, d.content, 
               1 - (d.embedding <-> :embedding::vector) as similarity
        FROM documents d
        ORDER BY d.embedding <-> :embedding::vector
        LIMIT :limit
    """)
    
    results = db.execute(
        sql, 
        {"embedding": str(list(query_embedding)), "limit": limit}
    ).fetchall()

    return [
        SearchResponse(
            id=row.id,
            filename=row.filename,
            content=row.content,
            similarity=float(row.similarity)
        ) for row in results
    ]
