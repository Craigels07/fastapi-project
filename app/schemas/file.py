from datetime import datetime
from pydantic import BaseModel

class FileBase(BaseModel):
    filename: str
    filetype: str
    filepath: str


class FileCreate(FileBase):
    pass

class FileResponse(FileBase):
    id: int
    uploaded_at: datetime

    class Config:
        from_attributes = True
