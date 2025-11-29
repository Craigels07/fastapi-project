"""
WhatsApp Phone Number Management Router
Handles CRUD operations for managing multiple phone numbers per organization.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount, AccountStatus
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber, PhoneNumberStatus
from app.service.twilio.tech_provider import TwilioTechProviderService
from app.auth.dependencies import get_current_user
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp/phone-numbers", tags=["whatsapp-phone-numbers"])

# Encryption for decrypting stored tokens
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


# Request/Response Models
class AddPhoneNumberRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format (e.g., +1234567890)")
    display_name: Optional[str] = Field(None, description="Display name for the WhatsApp profile")
    is_primary: bool = Field(default=False, description="Set as primary number for organization")


class UpdatePhoneNumberRequest(BaseModel):
    display_name: Optional[str] = Field(None, description="New display name")
    callback_url: Optional[str] = Field(None, description="New callback URL")
    status_callback_url: Optional[str] = Field(None, description="New status callback URL")


class PhoneNumberResponse(BaseModel):
    id: str
    code: str
    phone_number: str
    display_name: Optional[str]
    sender_sid: Optional[str]
    status: str
    is_primary: bool
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    organization_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all phone numbers for the organization. Super_admin can specify organization_id to view any org's numbers."""
    from app.models.user import Organization
    
    # Super admin can view phone numbers for any organization
    if current_user.role == "super_admin" and organization_id:
        target_org_id = organization_id
    else:
        target_org_id = current_user.organization_id
    
    organization = db.query(Organization).filter(
        Organization.id == target_org_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get WhatsApp account
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.organization_id == organization.id
    ).first()
    
    if not account:
        return []
    
    # Get all phone numbers
    phone_numbers = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.whatsapp_account_id == account.id
    ).all()
    
    return [
        PhoneNumberResponse(
            id=str(pn.id),
            code=pn.code,
            phone_number=pn.phone_number,
            display_name=pn.display_name,
            sender_sid=pn.sender_sid,
            status=pn.status.value,
            is_primary=pn.is_primary,
            created_at=pn.created_at.isoformat()
        )
        for pn in phone_numbers
    ]


@router.post("", response_model=PhoneNumberResponse)
async def add_phone_number(
    request: AddPhoneNumberRequest,
    organization_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new phone number to the organization's WhatsApp account. Super_admin can specify organization_id to add to any org."""
    from app.models.user import Organization
    
    # Super admin can add phone numbers to any organization
    if current_user.role == "super_admin" and organization_id:
        target_org_id = organization_id
    else:
        target_org_id = current_user.organization_id
    
    organization = db.query(Organization).filter(
        Organization.id == target_org_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get WhatsApp account
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.organization_id == organization.id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WhatsApp account not found. Please complete onboarding first."
        )
    
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WhatsApp account is not active (status: {account.status})"
        )
    
    # Check if phone number already exists
    existing = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.phone_number == request.phone_number
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered"
        )
    
    try:
        # Register sender with Twilio
        twilio_service = TwilioTechProviderService()
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        sender = await twilio_service.register_whatsapp_sender(
            subaccount_sid=account.twilio_subaccount_sid,
            subaccount_token=decrypt_token(account.twilio_auth_token),
            phone_number=request.phone_number,
            waba_id=account.waba_id,
            display_name=request.display_name or organization.name,
            callback_url=f"{backend_url}/webhooks/whatsapp/inbound",
            status_callback_url=f"{backend_url}/webhooks/whatsapp/status"
        )
        
        # If this should be primary, unset other primary numbers
        if request.is_primary:
            db.query(WhatsAppPhoneNumber).filter(
                WhatsAppPhoneNumber.whatsapp_account_id == account.id,
                WhatsAppPhoneNumber.is_primary == True
            ).update({"is_primary": False})
        
        # Create phone number record
        phone_number = WhatsAppPhoneNumber(
            whatsapp_account_id=account.id,
            phone_number=request.phone_number,
            display_name=request.display_name or organization.name,
            sender_sid=sender["sender_sid"],
            messaging_service_sid=sender.get("messaging_service_sid"),
            callback_url=f"{backend_url}/webhooks/whatsapp/inbound",
            status_callback_url=f"{backend_url}/webhooks/whatsapp/status",
            status=PhoneNumberStatus.ACTIVE,
            is_primary=request.is_primary
        )
        
        db.add(phone_number)
        db.commit()
        db.refresh(phone_number)
        
        logger.info(f"Added phone number {phone_number.code} to account {account.code}")
        
        return PhoneNumberResponse(
            id=str(phone_number.id),
            code=phone_number.code,
            phone_number=phone_number.phone_number,
            display_name=phone_number.display_name,
            sender_sid=phone_number.sender_sid,
            status=phone_number.status.value,
            is_primary=phone_number.is_primary,
            created_at=phone_number.created_at.isoformat()
        )
    
    except Exception as e:
        logger.error(f"Failed to add phone number: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add phone number: {str(e)}"
        )


@router.patch("/{phone_number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_number_id: UUID,
    request: UpdatePhoneNumberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a phone number's configuration"""
    from app.models.user import Organization
    
    organization = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get phone number
    phone_number = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.id == phone_number_id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Verify ownership (super_admin can update any phone number)
    if current_user.role != "super_admin" and phone_number.account.organization_id != organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this phone number"
        )
    
    try:
        # Update in Twilio if needed
        if any([request.display_name, request.callback_url, request.status_callback_url]):
            twilio_service = TwilioTechProviderService()
            account = phone_number.account
            
            await twilio_service.update_sender(
                subaccount_sid=account.twilio_subaccount_sid,
                subaccount_token=decrypt_token(account.twilio_auth_token),
                sender_sid=phone_number.sender_sid,
                callback_url=request.callback_url,
                status_callback_url=request.status_callback_url,
                display_name=request.display_name
            )
        
        # Update local record
        if request.display_name:
            phone_number.display_name = request.display_name
        if request.callback_url:
            phone_number.callback_url = request.callback_url
        if request.status_callback_url:
            phone_number.status_callback_url = request.status_callback_url
        
        db.commit()
        db.refresh(phone_number)
        
        logger.info(f"Updated phone number {phone_number.code}")
        
        return PhoneNumberResponse(
            id=str(phone_number.id),
            code=phone_number.code,
            phone_number=phone_number.phone_number,
            display_name=phone_number.display_name,
            sender_sid=phone_number.sender_sid,
            status=phone_number.status.value,
            is_primary=phone_number.is_primary,
            created_at=phone_number.created_at.isoformat()
        )
    
    except Exception as e:
        logger.error(f"Failed to update phone number: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update phone number: {str(e)}"
        )


@router.post("/{phone_number_id}/set-primary")
async def set_primary_phone_number(
    phone_number_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a phone number as the primary number for the organization"""
    from app.models.user import Organization
    
    organization = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get phone number
    phone_number = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.id == phone_number_id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Verify ownership (super_admin can modify any phone number)
    if current_user.role != "super_admin" and phone_number.account.organization_id != organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this phone number"
        )
    
    try:
        # Unset all other primary numbers for this account
        db.query(WhatsAppPhoneNumber).filter(
            WhatsAppPhoneNumber.whatsapp_account_id == phone_number.whatsapp_account_id,
            WhatsAppPhoneNumber.is_primary == True
        ).update({"is_primary": False})
        
        # Set this as primary
        phone_number.is_primary = True
        
        # Update organization's phone number
        organization.phone_number = phone_number.phone_number
        
        db.commit()
        
        logger.info(f"Set {phone_number.code} as primary for {organization.name}")
        
        return {"success": True, "message": "Primary phone number updated"}
    
    except Exception as e:
        logger.error(f"Failed to set primary phone number: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set primary phone number: {str(e)}"
        )


@router.delete("/{phone_number_id}")
async def delete_phone_number(
    phone_number_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a phone number from the organization"""
    from app.models.user import Organization
    
    organization = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get phone number
    phone_number = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.id == phone_number_id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Verify ownership (super_admin can delete any phone number)
    if current_user.role != "super_admin" and phone_number.account.organization_id != organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this phone number"
        )
    
    # Check if this is the only number
    total_numbers = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.whatsapp_account_id == phone_number.whatsapp_account_id
    ).count()
    
    if total_numbers == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the only phone number. Add another number first."
        )
    
    try:
        # Delete from Twilio
        twilio_service = TwilioTechProviderService()
        account = phone_number.account
        
        await twilio_service.delete_sender(
            subaccount_sid=account.twilio_subaccount_sid,
            subaccount_token=decrypt_token(account.twilio_auth_token),
            sender_sid=phone_number.sender_sid
        )
        
        # If this was primary, set another number as primary
        if phone_number.is_primary:
            other_number = db.query(WhatsAppPhoneNumber).filter(
                WhatsAppPhoneNumber.whatsapp_account_id == phone_number.whatsapp_account_id,
                WhatsAppPhoneNumber.id != phone_number.id
            ).first()
            
            if other_number:
                other_number.is_primary = True
                organization.phone_number = other_number.phone_number
        
        # Delete from database
        db.delete(phone_number)
        db.commit()
        
        logger.info(f"Deleted phone number {phone_number.code}")
        
        return {"success": True, "message": "Phone number deleted"}
    
    except Exception as e:
        logger.error(f"Failed to delete phone number: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete phone number: {str(e)}"
        )
