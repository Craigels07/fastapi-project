from passlib.context import CryptContext
import bcrypt
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


def verify_password(plain_password, hashed_password):
    """
    Verify a password against a hash
    """
    try:
        if isinstance(hashed_password, str) and (
            hashed_password.startswith("$2a$")
            or hashed_password.startswith("$2b$")
            or hashed_password.startswith("$2y$")
        ):
            pw_bytes = plain_password.encode("utf-8") if isinstance(plain_password, str) else plain_password
            hp_bytes = hashed_password.encode("utf-8")
            ok = bcrypt.checkpw(pw_bytes[:72], hp_bytes)
            logger.debug("verify_password legacy_bcrypt result=%s", ok)
            return ok
        ok = pwd_context.verify(plain_password, hashed_password)
        logger.debug("verify_password context result=%s", ok)
        return ok
    except Exception:
        logger.exception("verify_password exception")
        return False


def get_password_hash(password):
    """
    Hash a password for storage
    Truncates to 72 bytes to comply with bcrypt's limit
    """
    # Convert to bytes and truncate to 72 bytes (bcrypt limit)
    pw_bytes = password.encode("utf-8") if isinstance(password, str) else password
    truncated_pw_bytes = pw_bytes[:72]
    
    # Use bcrypt directly to avoid passlib's internal initialization issues
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(truncated_pw_bytes, salt)
    return hashed.decode("utf-8")


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user by email and password

    Returns the user if authentication succeeds, None otherwise
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not hasattr(user, "password"):
        return None
    if not verify_password(password, user.password):
        return None
    return user
