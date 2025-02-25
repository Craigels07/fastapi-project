from http.client import HTTPException
from fastapi import APIRouter, UploadFile, File, Depends
import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.file import File
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
    return create_file(db, file_data)

@router.get("/", response_model=FileResponse)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    file = get_file_by_id(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@router.get("/", response_model=list[FileResponse])
async def get_all_files(db: Session = Depends(get_db)):
    return get_all_files(db)
