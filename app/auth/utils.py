from passlib.context import CryptContext
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    """
    Verify a password against a hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    Hash a password for storage
    """
    return pwd_context.hash(password)


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user by email and password

    Returns the user if authentication succeeds, None otherwise
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not hasattr(user, "password"):
        # If you haven't added a password field to your user model yet
        return None
    if not verify_password(password, user.password):
        return None
    return user
