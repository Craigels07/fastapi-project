from app.service.llama_index import LlamaIndexService
from app.models.file import File
from app.models.documents import Document
from sqlalchemy.orm import Session
import numpy as np


def store_document(db: Session, file_id: int, text: str):
    llama_index_service = LlamaIndexService()
    embedding = llama_index_service.get_embedding(text)

    # embedding_str = f"ARRAY{np.array(embedding).tolist()}"
    embedding_str = "{" + ",".join(map(str, embedding)) + "}"

    db.execute(
        "INSERT INTO documents (file_id, content, embedding) VALUES (:file_id, :content, :embedding::vector)",
        {"file_id": file_id, "content": text, "embedding": embedding_str},
    )
    db.commit()

def search_documents(db: Session, query: str):
    llama_index_service = LlamaIndexService()
    query_embedding = llama_index_service.get_embedding(query)

    # embedding_str = f"ARRAY{np.array(query_embedding).tolist()}"
    embedding_str = "{" + ",".join(map(str, query_embedding)) + "}"

    result = db.execute(
        "SELECT content FROM documents ORDER BY embedding <-> :embedding::vector LIMIT 5",
        {"embedding": embedding_str}
    ).fetchall()

    return [row[0] for row in result]
