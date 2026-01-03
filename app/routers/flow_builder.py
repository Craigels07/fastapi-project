"""
Flow Builder API Endpoints
Provides endpoints for configuring and testing flow nodes in the builder UI.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from app.database import get_db
from app.models.user import User
from app.models.whatsapp import WhatsAppUser, WhatsAppThread
from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.auth.dependencies import get_current_user
from app.helpers.compliance_helper import can_send_freeform_message, get_window_status
from twilio.rest import Client
from cryptography.fernet import Fernet
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flow-builder", tags=["flow-builder"])

# Encryption for decrypting stored tokens
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


# Request/Response Models
class TestMessageRequest(BaseModel):
    """Request to test a send-message node"""
    phone_number: str = Field(..., description="Test recipient phone number (E.164 format)")
    message_body: str = Field(..., description="Message content to send")
    buttons: Optional[List[Dict[str, str]]] = Field(default=None, description="Optional buttons")
    delay_seconds: Optional[int] = Field(default=0, description="Delay before sending")


class TestMessageResponse(BaseModel):
    """Response from test message send"""
    success: bool
    message_sid: Optional[str] = None
    status: str
    compliance_status: Dict[str, Any]
    error: Optional[str] = None


class WebhookConfigRequest(BaseModel):
    """Request to configure a webhook node"""
    webhook_url: str = Field(..., description="External webhook URL to call")
    method: str = Field(default="POST", description="HTTP method (GET, POST)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Custom headers")
    timeout_seconds: Optional[int] = Field(default=30, description="Request timeout")


class WebhookConfigResponse(BaseModel):
    """Response from webhook configuration"""
    success: bool
    webhook_id: str
    test_url: str
    message: str


class WebhookTestRequest(BaseModel):
    """Request to test a webhook configuration"""
    webhook_url: str
    method: str = "POST"
    headers: Optional[Dict[str, str]] = None
    test_payload: Optional[Dict[str, Any]] = None


class WebhookTestResponse(BaseModel):
    """Response from webhook test"""
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    response_time_ms: Optional[int] = None
    error: Optional[str] = None


class ComplianceCheckRequest(BaseModel):
    """Request to check compliance status for a user"""
    phone_number: str = Field(..., description="User phone number to check")


class ComplianceCheckResponse(BaseModel):
    """Response with compliance status"""
    phone_number: str
    opted_out: bool
    opted_out_at: Optional[str] = None
    window_status: Dict[str, Any]
    can_send_freeform: bool
    recommendations: List[str]


@router.post("/test-message", response_model=TestMessageResponse)
async def test_send_message(
    request: TestMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test a send-message node configuration.
    Sends a test message and returns compliance status.
    """
    try:
        # Get organization's WhatsApp account
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == current_user.organization_id
        ).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No WhatsApp account found for organization"
            )
        
        # Get primary phone number
        primary_phone = account.get_primary_phone_number()
        if not primary_phone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No phone numbers configured for WhatsApp account"
            )
        
        # Find or create test user
        test_user = db.query(WhatsAppUser).filter(
            WhatsAppUser.phone_number == request.phone_number,
            WhatsAppUser.organization_id == current_user.organization_id
        ).first()
        
        if not test_user:
            test_user = WhatsAppUser(
                phone_number=request.phone_number,
                profile_name="Test User",
                organization_id=current_user.organization_id,
                opted_out=False
            )
            db.add(test_user)
            db.flush()
        
        # Find or create test thread
        test_thread = db.query(WhatsAppThread).filter(
            WhatsAppThread.user_id == test_user.id,
            WhatsAppThread.is_active == True
        ).first()
        
        if not test_thread:
            test_thread = WhatsAppThread(
                user_id=test_user.id,
                organization_id=current_user.organization_id,
                topic="Flow Builder Test",
                is_active=True
            )
            db.add(test_thread)
            db.flush()
        
        # Check compliance status
        compliance_status = {
            "opted_out": test_user.opted_out,
            "window_status": get_window_status(test_thread),
            "can_send_freeform": can_send_freeform_message(test_thread)
        }
        
        # Block if user opted out
        if test_user.opted_out:
            return TestMessageResponse(
                success=False,
                status="blocked",
                compliance_status=compliance_status,
                error="User has opted out. Cannot send message."
            )
        
        # Warn if outside 24-hour window
        if not can_send_freeform_message(test_thread):
            logger.warning(f"Test message outside 24-hour window for {request.phone_number}")
        
        # Prepare message with buttons
        final_message = request.message_body
        if request.buttons and len(request.buttons) > 0:
            final_message += "\n\n"
            for i, button in enumerate(request.buttons[:3], 1):
                button_text = button.get("text", "")
                if button_text:
                    final_message += f"{i}. {button_text}\n"
        
        # Send via Twilio using Messaging Service
        auth_token = decrypt_token(account.twilio_auth_token)
        client = Client(account.twilio_subaccount_sid, auth_token)
        
        if account.messaging_service_sid:
            twilio_message = client.messages.create(
                messaging_service_sid=account.messaging_service_sid,
                to=f"whatsapp:{request.phone_number}",
                body=final_message
            )
        else:
            # Fallback for legacy accounts
            twilio_message = client.messages.create(
                from_=f"whatsapp:{primary_phone.phone_number}",
                to=f"whatsapp:{request.phone_number}",
                body=final_message
            )
        
        db.commit()
        
        return TestMessageResponse(
            success=True,
            message_sid=twilio_message.sid,
            status=twilio_message.status,
            compliance_status=compliance_status
        )
        
    except Exception as e:
        logger.error(f"Error testing message: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test message: {str(e)}"
        )


@router.post("/test-webhook", response_model=WebhookTestResponse)
async def test_webhook(
    request: WebhookTestRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test a webhook configuration by sending a test request.
    """
    import httpx
    import time
    
    try:
        # Prepare test payload
        test_payload = request.test_payload or {
            "event": "test",
            "timestamp": datetime.utcnow().isoformat(),
            "test_mode": True,
            "organization_id": str(current_user.organization_id)
        }
        
        # Prepare headers
        headers = request.headers or {}
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "FlowBuilder-WebhookTest/1.0"
        
        # Send test request
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if request.method.upper() == "POST":
                response = await client.post(
                    request.webhook_url,
                    json=test_payload,
                    headers=headers
                )
            else:
                response = await client.get(
                    request.webhook_url,
                    headers=headers
                )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        return WebhookTestResponse(
            success=response.status_code < 400,
            status_code=response.status_code,
            response_body=response.text[:500],  # Limit response size
            response_time_ms=response_time_ms
        )
        
    except httpx.TimeoutException:
        return WebhookTestResponse(
            success=False,
            error="Webhook request timed out"
        )
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        return WebhookTestResponse(
            success=False,
            error=str(e)
        )


@router.post("/check-compliance", response_model=ComplianceCheckResponse)
async def check_compliance(
    request: ComplianceCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check compliance status for a specific user.
    Useful for the builder to show warnings/recommendations.
    """
    try:
        # Find user
        user = db.query(WhatsAppUser).filter(
            WhatsAppUser.phone_number == request.phone_number,
            WhatsAppUser.organization_id == current_user.organization_id
        ).first()
        
        if not user:
            # User doesn't exist yet - all clear
            return ComplianceCheckResponse(
                phone_number=request.phone_number,
                opted_out=False,
                window_status={
                    "within_window": True,
                    "hours_remaining": 24.0,
                    "message": "New user - no restrictions"
                },
                can_send_freeform=True,
                recommendations=["User has not interacted yet. First message will open 24-hour window."]
            )
        
        # Find active thread
        thread = db.query(WhatsAppThread).filter(
            WhatsAppThread.user_id == user.id,
            WhatsAppThread.is_active == True
        ).first()
        
        # Get compliance status
        window_status = get_window_status(thread) if thread else {
            "within_window": False,
            "hours_remaining": 0,
            "message": "No active conversation"
        }
        
        can_send = can_send_freeform_message(thread) if thread else False
        
        # Generate recommendations
        recommendations = []
        if user.opted_out:
            recommendations.append("⛔ User has opted out. No messages can be sent.")
            recommendations.append("User must send START to opt back in.")
        elif not can_send:
            recommendations.append("⏰ 24-hour window expired. Use a template message instead.")
            recommendations.append("Or wait for user to send a message to reopen window.")
        else:
            recommendations.append("✅ All clear - can send freeform messages.")
        
        return ComplianceCheckResponse(
            phone_number=request.phone_number,
            opted_out=user.opted_out,
            opted_out_at=user.opted_out_at.isoformat() if user.opted_out_at else None,
            window_status=window_status,
            can_send_freeform=can_send,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error checking compliance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check compliance: {str(e)}"
        )


@router.get("/webhook-info")
async def get_webhook_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get webhook URLs and configuration info for the organization.
    Useful for displaying in the builder UI.
    """
    try:
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        # Get organization's phone numbers
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == current_user.organization_id
        ).first()
        
        phone_numbers = []
        if account:
            for phone in account.phone_numbers:
                phone_numbers.append({
                    "phone_number": phone.phone_number,
                    "display_name": phone.display_name,
                    "is_primary": phone.is_primary,
                    "status": phone.status.value,
                    "inbound_webhook": phone.callback_url or f"{backend_url}/webhooks/whatsapp/inbound",
                    "status_webhook": phone.status_callback_url or f"{backend_url}/webhooks/whatsapp/status"
                })
        
        return {
            "backend_url": backend_url,
            "inbound_webhook": f"{backend_url}/webhooks/whatsapp/inbound",
            "status_webhook": f"{backend_url}/webhooks/whatsapp/status",
            "phone_numbers": phone_numbers,
            "messaging_service_sid": account.messaging_service_sid if account else None,
            "compliance_enabled": True
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get webhook info: {str(e)}"
        )
