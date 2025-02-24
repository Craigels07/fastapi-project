from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate
from app.crud.user import create_user

router = APIRouter()


@router.post("/users/")
def create_new_user(user: UserCreate, db: Session = Depends(get_db)) -> UserCreate:
    return create_user(db, user)
