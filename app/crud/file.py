from sqlalchemy.orm import Session
from app.models.file import File
from app.schemas.file import FileCreate


def create_file(db: Session, file_data: FileCreate):
    db_file = File(**file_data.dict())
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file  # Return ORM object instead of dict
    # return {"filename": db_file.filename, "status": "File uploaded successfully"}


def get_file_by_id(db: Session, file_id: int):
    return db.query(File).filter(File.id == file_id).first()


def get_all_files(db: Session):
    return db.query(File).all()
