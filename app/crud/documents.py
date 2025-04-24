from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.pgvector import PGVector
from langchain_core.documents import Document as LangchainDocument
from app.schemas.document import DocumentResponse
from app.helpers.collection_helpers import get_or_create_collection
from app.schemas.documents import DocumentCreate
import mimetypes
from app.models.documents import Document
from app.service.llama_index import get_document_loader
from uuid import uuid4
from fastapi.encoders import jsonable_encoder

from dotenv import load_dotenv
import os

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

    collection = get_or_create_collection(db, "UDM")

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents([text_content])

    # Embedding
    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model="text-embedding-3-small")

    # Vector store
    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name=collection.name,
        connection=DATABASE_URL,
        use_jsonb=True,
    )

    doc_data = DocumentCreate(
        filename=file.filename,
        content_type=file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream",
        filepath=str(file_path),
        preview=text_content[:300],  # Just a short snippet
        doc_metadata={"filename": file.filename, "num_chunks": len(chunks)},
        collection_id=collection.id
    )

    document = Document(**doc_data.dict())
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
                    "source": "upload",
                }
            )
        )

    vectorstore.add_documents(docs, ids=[doc.metadata["id"] for doc in docs])

    return [DocumentResponse(**jsonable_encoder(document))]

