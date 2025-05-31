from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.models.whatsapp import WhatsAppUser
from app.models.user import Organization


def get_whatsapp_user(db: Session, user_id: UUID) -> Optional[WhatsAppUser]:
    """
    Get a WhatsApp user by ID
    """
    return db.query(WhatsAppUser).filter(WhatsAppUser.id == user_id).first()


def update_whatsapp_user_organization(
    db: Session, user_id: UUID, organization_id: UUID
) -> Optional[WhatsAppUser]:
    """
    Update a WhatsApp user's organization
    """
    db_user = get_whatsapp_user(db, user_id)
    if not db_user:
        return None

    # Verify organization exists
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        return None

    db_user.organization_id = organization_id
    db.commit()
    db.refresh(db_user)
    return db_user
