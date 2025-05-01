from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredImageLoader,
    CSVLoader,
    UnstructuredExcelLoader
)
from pathlib import Path
from fastapi import HTTPException

LOADER_MAPPING = {
    # Map file extensions to LangChain document loaders
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

def get_document_loader(file_path: str):
    """Get the appropriate document loader based on file extension"""
    ext = Path(file_path).suffix.lower()
    if ext in LOADER_MAPPING:
        return LOADER_MAPPING[ext]
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: {ext}. Supported types: {', '.join(LOADER_MAPPING.keys())}"
    )