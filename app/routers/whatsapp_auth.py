"""
WhatsApp Tech Provider Authentication Router
Handles WhatsApp Business Account onboarding and management
using Twilio's Tech Provider Program with Meta's Embedded Signup.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_db
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount, AccountStatus
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber, PhoneNumberStatus
from app.service.twilio.tech_provider import TwilioTechProviderService
from app.auth.dependencies import get_current_user
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp-auth"])

# Encryption for storing sensitive tokens
# In production, load this from environment variable
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)


def encrypt_token(token: str) -> str:
    """Encrypt a token for secure storage"""
    return cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


# Request/Response Models
class PhoneNumberRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format (e.g., +1234567890)")
    is_twilio_number: bool = Field(default=False, description="Whether this is a Twilio-assigned number")


class EmbeddedSignupCallback(BaseModel):
    waba_id: str = Field(..., description="WhatsApp Business Account ID from Meta")
    phone_number: str = Field(..., description="Phone number in E.164 format")
    business_portfolio_id: Optional[str] = Field(None, description="Meta Business Portfolio ID")


class OnboardingResponse(BaseModel):
    account_id: str
    phone_number: str
    meta_config: dict
    next_step: str


class WhatsAppStatusResponse(BaseModel):
    connected: bool
    phone_number: Optional[str] = None
    display_name: Optional[str] = None
    waba_id: Optional[str] = None
    status: Optional[str] = None


@router.post("/start-onboarding", response_model=OnboardingResponse)
async def start_onboarding(
    request: PhoneNumberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 1: Start WhatsApp onboarding process
    - Creates a Twilio subaccount for the organization
    - Returns Meta app configuration for Embedded Signup
    """
    try:
        # Get user's organization
        from app.models.user import Organization
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization"
            )
        
        # Check if organization already has an active WhatsApp account
        existing_account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == organization.id,
            WhatsAppAccount.status.in_([AccountStatus.ACTIVE, AccountStatus.PENDING])
        ).first()
        
        if existing_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization already has an active WhatsApp account. Please disconnect first."
            )
        
        # Create Twilio subaccount
        twilio_service = TwilioTechProviderService()
        subaccount = await twilio_service.create_subaccount(
            customer_name=f"{organization.name} - WhatsApp"
        )
        
        # Create WhatsApp account record
        whatsapp_account = WhatsAppAccount(
            organization_id=organization.id,
            twilio_subaccount_sid=subaccount["account_sid"],
            twilio_auth_token=encrypt_token(subaccount["auth_token"]),
            phone_number=request.phone_number,
            status=AccountStatus.PENDING
        )
        
        db.add(whatsapp_account)
        db.commit()
        db.refresh(whatsapp_account)
        
        logger.info(f"Created WhatsApp account {whatsapp_account.code} for organization {organization.name}")
        
        # Return Meta configuration for Embedded Signup
        return OnboardingResponse(
            account_id=str(whatsapp_account.id),
            phone_number=request.phone_number,
            meta_config={
                "app_id": os.getenv("META_APP_ID"),
                "configuration_id": os.getenv("META_CONFIGURATION_ID"),
                "partner_solution_id": os.getenv("PARTNER_SOLUTION_ID")
            },
            next_step="embedded_signup"
        )
    
    except Exception as e:
        logger.error(f"Failed to start onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start onboarding: {str(e)}"
        )


@router.post("/complete-signup")
async def complete_embedded_signup(
    callback: EmbeddedSignupCallback,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 2: Complete Embedded Signup
    - Called after user completes Meta's Embedded Signup flow
    - Registers WhatsApp sender with Twilio
    - Updates organization phone_number for webhook routing
    """
    try:
        # Get user's organization
        from app.models.user import Organization
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization"
            )
        
        # Find pending account
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == organization.id,
            WhatsAppAccount.phone_number == callback.phone_number,
            WhatsAppAccount.status == AccountStatus.PENDING
        ).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding session not found. Please start onboarding again."
            )
        
        # Update account with WABA information
        account.waba_id = callback.waba_id
        account.meta_business_portfolio_id = callback.business_portfolio_id
        
        # Register sender with Twilio
        twilio_service = TwilioTechProviderService()
        
        # Get backend URL for webhooks
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        sender = await twilio_service.register_whatsapp_sender(
            subaccount_sid=account.twilio_subaccount_sid,
            subaccount_token=decrypt_token(account.twilio_auth_token),
            phone_number=callback.phone_number,
            waba_id=callback.waba_id,
            display_name=current_user.name or current_user.email,
            callback_url=f"{backend_url}/webhooks/whatsapp/inbound",
            status_callback_url=f"{backend_url}/webhooks/whatsapp/status"
        )
        
        # Create phone number record (first number for this account)
        phone_number = WhatsAppPhoneNumber(
            whatsapp_account_id=account.id,
            phone_number=callback.phone_number,
            display_name=organization.name,
            sender_sid=sender["sender_sid"],
            messaging_service_sid=sender.get("messaging_service_sid"),
            callback_url=f"{backend_url}/webhooks/whatsapp/inbound",
            status_callback_url=f"{backend_url}/webhooks/whatsapp/status",
            status=PhoneNumberStatus.ACTIVE,
            is_primary=True  # First number is always primary
        )
        db.add(phone_number)
        
        # Update account status
        account.status = AccountStatus.ACTIVE
        
        # Update organization phone number for webhook routing (backward compatibility)
        organization.phone_number = callback.phone_number
        
        db.commit()
        
        logger.info(f"Completed WhatsApp signup for account {account.code}")
        
        return {
            "success": True,
            "account_id": str(account.id),
            "sender_id": sender["sender_id"],
            "status": "active"
        }
    
    except Exception as e:
        logger.error(f"Failed to complete signup: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete signup: {str(e)}"
        )


@router.get("/status", response_model=WhatsAppStatusResponse)
async def get_whatsapp_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current WhatsApp connection status for the organization"""
    from app.models.user import Organization
    organization = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    if not organization:
        return WhatsAppStatusResponse(connected=False)
    
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.organization_id == organization.id
    ).order_by(WhatsAppAccount.created_at.desc()).first()
    
    if not account:
        return WhatsAppStatusResponse(connected=False)
    
    # Get primary phone number
    primary_phone = account.get_primary_phone_number()
    
    return WhatsAppStatusResponse(
        connected=account.status == AccountStatus.ACTIVE,
        phone_number=primary_phone.phone_number if primary_phone else None,
        display_name=primary_phone.display_name if primary_phone else None,
        waba_id=account.waba_id,
        status=account.status.value
    )


@router.delete("/disconnect")
async def disconnect_whatsapp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect WhatsApp account
    - Suspends the Twilio subaccount
    - Marks account as suspended
    """
    try:
        from app.models.user import Organization
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == organization.id,
            WhatsAppAccount.status == AccountStatus.ACTIVE
        ).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active WhatsApp account found"
            )
        
        # Suspend Twilio subaccount
        twilio_service = TwilioTechProviderService()
        await twilio_service.suspend_subaccount(account.twilio_subaccount_sid)
        
        # Update account status
        account.status = AccountStatus.SUSPENDED
        db.commit()
        
        logger.info(f"Disconnected WhatsApp account {account.code}")
        
        return {"success": True, "message": "WhatsApp account disconnected"}
    
    except Exception as e:
        logger.error(f"Failed to disconnect WhatsApp: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect: {str(e)}"
        )


@router.post("/reconnect")
async def reconnect_whatsapp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reconnect a suspended WhatsApp account
    - Reactivates the Twilio subaccount
    """
    try:
        from app.models.user import Organization
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == organization.id,
            WhatsAppAccount.status == AccountStatus.SUSPENDED
        ).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suspended WhatsApp account found"
            )
        
        # Reactivate Twilio subaccount
        twilio_service = TwilioTechProviderService()
        await twilio_service.reactivate_subaccount(account.twilio_subaccount_sid)
        
        # Update account status
        account.status = AccountStatus.ACTIVE
        db.commit()
        
        logger.info(f"Reconnected WhatsApp account {account.code}")
        
        return {"success": True, "message": "WhatsApp account reconnected"}
    
    except Exception as e:
        logger.error(f"Failed to reconnect WhatsApp: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reconnect: {str(e)}"
        )
