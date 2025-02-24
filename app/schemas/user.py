from pydantic import BaseModel

class UserCreate(BaseModel):
    id: int
    name: str
    email: str
