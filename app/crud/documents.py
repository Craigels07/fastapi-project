from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document as LangchainDocument
from app.schemas.document import DocumentResponse, DocumentCreate
from app.helpers.collection_helpers import get_or_create_collection
import mimetypes
from app.models.documents import Document
from app.helpers.document_helper import get_document_loader
from uuid import uuid4
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
from typing import List
from app.schemas.document import SearchResponse

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


async def process_and_store_document(db, file, file_path):
    """Process and store a document with vector embeddings"""
    # Load and process document
    loader_class = get_document_loader(file_path)
    loader = loader_class(str(file_path))
    documents = loader.load()
    text_content = "\n\n".join(doc.page_content for doc in documents)

    collection = get_or_create_collection(db, "craig_test")

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents([text_content])

    # Embedding
    embeddings = OpenAIEmbeddings(
        api_key=OPENAI_API_KEY, model="text-embedding-3-small"
    )

    vectorstore = PGVector(
        connection=DATABASE_URL,
        collection_name=collection.name,
        embeddings=embeddings,
        use_jsonb=True,
    )

    doc_data = DocumentCreate(
        content_type=file.content_type
        or mimetypes.guess_type(file.filename)[0]
        or "application/octet-stream",
        filepath=str(file_path),
        preview=text_content[:300],  # Just a short snippet
        doc_metadata={"filename": file.filename, "num_chunks": len(chunks)},
        collection_id=collection.id,
    )

    document = Document(**doc_data.model_dump())
    db.add(document)
    db.commit()
    db.refresh(document)

    docs = []

    for chunk in chunks:
        docs.append(
            LangchainDocument(
                page_content=chunk.page_content,
                metadata={
                    "id": str(uuid4()),
                    "document_id": document.id,
                    "filename": file.filename,
                    "collection": collection.name,
                    "collection_id": collection.id,
                    "preview": text_content[:300],
                    "source": "upload",
                },
            )
        )

    vectorstore.add_documents(docs, ids=[doc.metadata["id"] for doc in docs])

    return [DocumentResponse(**jsonable_encoder(document))]


def search_documents(db: Session, query: str, limit: int = 5) -> List[SearchResponse]:
    """Search documents using semantic similarity"""

    responses = []

    collection = get_or_create_collection(db, "craig_test")

    embeddings = OpenAIEmbeddings(
        api_key=OPENAI_API_KEY, model="text-embedding-3-small"
    )

    vectorstore = PGVector(
        connection=DATABASE_URL,
        collection_name=collection.name,
        embeddings=embeddings,
        use_jsonb=True,
    )
    results = vectorstore.similarity_search(query, k=limit)

    for result in results:
        responses.append(
            SearchResponse(
                id=result.metadata.get("document_id") or result.metadata.get("id"),
                filename=result.metadata.get("filename"),
                preview=result.metadata.get("preview", ""),
                collection_id=result.metadata.get("collection_id") or 0,
                similarity=result.metadata.get("similarity", 1.0),
            )
        )

    return responses
