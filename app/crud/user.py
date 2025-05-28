from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import APIRouter, Depends
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    OrganizationCreate,
    OrganizationRead,
)
from app.models.user import Organization

router = APIRouter()


@router.post("/organizations/", response_model=OrganizationRead, status_code=201)
def create_organization(
    organization: OrganizationCreate, db: Session = Depends(get_db)
) -> Organization:
    new_org = Organization(
        name=organization.name,
        email=organization.email,
        phone_number=organization.phone_number,
        organization_metadata=organization.organization_metadata,
        woo_commerce=organization.woo_commerce,
    )
    db.add(new_org)
    db.commit()
    db.refresh(new_org)
    return new_org


def create_user(db: Session, user: UserCreate) -> User:
    new_user = User(
        name=user.name,
        email=user.email,
        phone_number=user.phone_number,
        organization_id=user.organization_id,
        role=user.role,
        status=user.status,
        user_metadata=user.user_metadata,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def update_user(db: Session, user_id: int, user: UserUpdate) -> Optional[User]:
    db_user = get_user(db, user_id)
    if db_user:
        update_data = user.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        db.commit()
        db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False
