from http.client import HTTPException
from app.crud.llama_index import store_document
from fastapi import APIRouter, UploadFile, File, Depends
import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.file import FileCreate, FileResponse
from app.crud.file import create_file, get_file_by_id, get_all_files

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/", response_model=FileResponse)
async def upload_file(file: UploadFile = File(), db: Session = Depends(get_db)):
    file_path = Path(UPLOAD_DIR) / file.filename
    with file_path.open("wb") as buffer:
        buffer.write(await file.read())

    file_data = FileCreate(filename=file.filename, filetype=file.content_type, filepath=str(file_path))
    saved_file = create_file(db, file_data)

    if file.content_type.startswith("text"):
        with open(file_path, "r") as f:
            content = f.read()
            store_document(db, file.id, content)

    return saved_file

@router.get("/file", response_model=FileResponse)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    file = get_file_by_id(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@router.get("/files", response_model=list[FileResponse])
async def list_all_files(db: Session = Depends(get_db)):
    return get_all_files(db)
