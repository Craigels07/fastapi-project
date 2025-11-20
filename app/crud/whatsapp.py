from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import func, and_

from app.models.whatsapp import WhatsAppUser, WhatsAppThread, WhatsAppMessage
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


def get_threads_by_organization(
    db: Session, organization_id: UUID
) -> List[WhatsAppThread]:
    """
    Get all threads for an organization with user info and last message
    """
    threads = (
        db.query(WhatsAppThread)
        .filter(WhatsAppThread.organization_id == organization_id)
        .order_by(WhatsAppThread.updated_at.desc())
        .all()
    )
    return threads


def get_thread_messages(db: Session, thread_id: UUID) -> List[WhatsAppMessage]:
    """
    Get all messages for a specific thread
    """
    messages = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.thread_id == thread_id)
        .order_by(WhatsAppMessage.timestamp.asc())
        .all()
    )
    return messages


def get_whatsapp_users_by_organization(
    db: Session, organization_id: UUID
) -> List[WhatsAppUser]:
    """
    Get all WhatsApp users for an organization
    """
    users = (
        db.query(WhatsAppUser)
        .filter(WhatsAppUser.organization_id == organization_id)
        .all()
    )
    return users


def get_organization_stats(db: Session, organization_id: UUID) -> dict:
    """
    Get statistics for an organization's WhatsApp activity
    """
    # Total conversations (unique WhatsApp users)
    total_conversations = (
        db.query(func.count(WhatsAppUser.id))
        .filter(WhatsAppUser.organization_id == organization_id)
        .scalar()
    )

    # Active threads
    active_threads = (
        db.query(func.count(WhatsAppThread.id))
        .filter(
            and_(
                WhatsAppThread.organization_id == organization_id,
                WhatsAppThread.is_active,
            )
        )
        .scalar()
    )

    # Messages today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = (
        db.query(func.count(WhatsAppMessage.id))
        .join(WhatsAppUser)
        .filter(
            and_(
                WhatsAppUser.organization_id == organization_id,
                WhatsAppMessage.timestamp >= today_start.isoformat(),
            )
        )
        .scalar()
    )

    return {
        "total_conversations": total_conversations or 0,
        "active_threads": active_threads or 0,
        "messages_today": messages_today or 0,
    }


def get_recent_messages(
    db: Session, organization_id: UUID, limit: int = 10
) -> List[WhatsAppMessage]:
    """
    Get recent messages for an organization
    """
    messages = (
        db.query(WhatsAppMessage)
        .join(WhatsAppUser)
        .filter(WhatsAppUser.organization_id == organization_id)
        .order_by(WhatsAppMessage.timestamp.desc())
        .limit(limit)
        .all()
    )
    return messages
