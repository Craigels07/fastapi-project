"""
WhatsApp Webhook Handlers
Handles inbound messages and status updates from Twilio.
Uses Tech Provider accounts with existing message/thread models.
"""

import os
from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.models.whatsapp import WhatsAppUser, WhatsAppMessage, WhatsAppThread
from app.models.user import Organization
from app.crud import flow as flow_crud
from app.service.flow_executor import execute_flow
from app.agent.whatsapp_agent import WhatsAppAgent
from app.helpers.whatsapp_helper import model_with_tools
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from cryptography.fernet import Fernet
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhooks"])

# Twilio credentials for sending messages (main account fallback)
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

# Encryption for decrypting stored tokens
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


def validate_twilio_request(request: Request, form_data: dict) -> bool:
    """
    Validate that the request came from Twilio using signature validation.
    """
    skip_validation = os.getenv("SKIP_TWILIO_VALIDATION", "False").lower() == "true"
    if skip_validation:
        logger.warning("Twilio signature validation is disabled")
        return True
    
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set, cannot validate signature")
        return False
    
    validator = RequestValidator(auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    
    is_valid = validator.validate(url, form_data, signature)
    if not is_valid:
        logger.error(f"Invalid Twilio signature for URL: {url}")
    
    return is_valid


@router.post("/inbound")
async def whatsapp_inbound_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle inbound WhatsApp messages from Twilio.
    Uses Tech Provider accounts with existing message/thread models.
    Includes flow execution and agent workflow from the old system.
    """
    try:
        # Parse and validate form data from Twilio
        data = await request.form()
        form_data = dict(data)
        
        # Validate Twilio signature
        if not validate_twilio_request(request, form_data):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Twilio signature"
            )
        
        # Extract message data
        from_number = data.get("From", "").replace("whatsapp:", "")
        to_number = data.get("To", "").replace("whatsapp:", "")
        body = data.get("Body", "")
        message_sid = data.get("MessageSid")
        profile_name = data.get("ProfileName")
        wa_id = data.get("WaId")
        num_media = int(data.get("NumMedia", 0))
        
        logger.info(f"Received inbound message from {from_number} to {to_number}: {body[:50]}")
        
        # Find phone number record (supports multiple numbers per organization)
        phone_number_record = db.query(WhatsAppPhoneNumber).filter(
            WhatsAppPhoneNumber.phone_number == to_number
        ).first()
        
        if not phone_number_record:
            # Fallback: try finding organization by phone number (backward compatibility)
            organization = db.query(Organization).filter(
                Organization.phone_number == to_number
            ).first()
            
            if not organization:
                logger.warning(f"No phone number or organization found for {to_number}")
                return {"status": "error", "message": "Phone number not registered"}
            
            # Use main account credentials (old system)
            org_account_sid = account_sid
            org_auth_token = auth_token
            logger.info(f"Using main account for organization {organization.name} (legacy mode)")
        else:
            # Get organization via phone number's account
            organization = phone_number_record.account.organization
            
            # Use subaccount credentials from the account
            org_account_sid = phone_number_record.account.twilio_subaccount_sid
            org_auth_token = decrypt_token(phone_number_record.account.twilio_auth_token)
            logger.info(f"Using subaccount {org_account_sid} for {organization.name} via {phone_number_record.code}")
        
        # Find or create WhatsApp user
        whatsapp_user = db.query(WhatsAppUser).filter(
            WhatsAppUser.phone_number == from_number,
            WhatsAppUser.organization_id == organization.id
        ).first()
        
        if not whatsapp_user:
            whatsapp_user = WhatsAppUser(
                phone_number=from_number,
                profile_name=profile_name,
                organization_id=organization.id
            )
            db.add(whatsapp_user)
            db.flush()
        
        # Find or create active thread
        active_thread = db.query(WhatsAppThread).filter(
            WhatsAppThread.user_id == whatsapp_user.id,
            WhatsAppThread.organization_id == organization.id,
            WhatsAppThread.is_active.is_(True)
        ).first()
        
        if not active_thread:
            active_thread = WhatsAppThread(
                user_id=whatsapp_user.id,
                organization_id=organization.id,
                topic=f"Conversation with {profile_name or from_number}",
                is_active=True
            )
            db.add(active_thread)
            db.flush()
        
        # Create message record
        message = WhatsAppMessage(
            user_id=whatsapp_user.id,
            thread_id=active_thread.id,
            direction="inbound",
            role=WhatsAppMessage.ROLE["USER"],
            content=body,
            timestamp=datetime.now().isoformat(),
            message_sid=message_sid,
            wa_id=wa_id,
            profile_name=profile_name,
            num_media=num_media,
            message_type=form_data.get("MessageType"),
            num_segments=form_data.get("NumSegments"),
            message_metadata=form_data
        )
        
        db.add(message)
        active_thread.updated_at = datetime.now()
        db.commit()
        db.refresh(message)
        
        logger.info(f"Saved inbound message {message.code}")
        
        # Check if there's a matching flow for this message
        matched_flow = flow_crud.match_flow_trigger(db, organization.id, body)
        
        if matched_flow:
            logger.info(f"Matched flow: {matched_flow.code} - {matched_flow.name}")
            
            # Execute the flow
            flow_response = execute_flow(matched_flow, body, from_number)
            
            if flow_response:
                # Send the flow response via Twilio
                twilio_client = Client(account_sid, auth_token)
                twilio_client.messages.create(
                    body=flow_response,
                    from_=f"whatsapp:{to_number}",
                    to=f"whatsapp:{from_number}"
                )
                
                # Store the outbound response message
                response_message = WhatsAppMessage(
                    user_id=whatsapp_user.id,
                    thread_id=active_thread.id,
                    content=flow_response,
                    direction="outbound",
                    role=WhatsAppMessage.ROLE["AGENT"],
                    timestamp=datetime.now().isoformat(),
                )
                db.add(response_message)
                db.commit()
                
                return {"status": "received", "message_id": str(message.id), "flow_executed": True}
        
        # No flow matched, use the agent workflow
        logger.info("No flow matched, using agent workflow")
        
        # Create a WhatsApp agent with tools using organization's credentials
        llm_with_tools = model_with_tools()
        whatsapp_agent = WhatsAppAgent(
            account_sid=org_account_sid,
            auth_token=org_auth_token,
            model=llm_with_tools,
            organization_id=organization.id,
            to_number=to_number,
        )
        
        # Process the message through the agent workflow
        agent_result = await whatsapp_agent.run(
            user_input=body,
            whatsapp_message_id=message.id,
            user_phone_number=from_number
        )
        
        return {"status": "received", "message_id": str(message.id), "agent_processed": True}
    
    except Exception as e:
        logger.error(f"Error processing inbound webhook: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status")
async def whatsapp_status_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle WhatsApp message status updates from Twilio.
    Statuses: queued, sent, delivered, read, failed, undelivered
    """
    try:
        # Parse form data from Twilio
        data = await request.form()
        
        message_sid = data.get("MessageSid")
        message_status = data.get("MessageStatus")  # sent, delivered, read, failed
        error_code = data.get("ErrorCode")
        error_message = data.get("ErrorMessage")
        
        logger.info(f"Received status update for message {message_sid}: {message_status}")
        
        # Find the message
        message = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.message_sid == message_sid
        ).first()
        
        if message:
            # Update message status
            message.sms_status = message_status
            
            # Add error information if present
            if error_code or error_message:
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata["error_code"] = error_code
                message.message_metadata["error_message"] = error_message
            
            db.commit()
            logger.info(f"Updated message {message.code} status to {message_status}")
        else:
            logger.warning(f"Message not found for SID {message_sid}")
        
        return {"status": "processed"}
    
    except Exception as e:
        logger.error(f"Error processing status webhook: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
