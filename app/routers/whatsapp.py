import os
from fastapi import APIRouter, Request, Form
from dotenv import load_dotenv
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from app.helpers.whatsapp_helper import send_whatsapp_message, model_with_tools
from fastapi.responses import JSONResponse
from app.agent.whatsapp_agent import WhatsAppAgent
from app.models.user import Organization
from app.models.whatsapp import WhatsAppUser, WhatsAppMessage, WhatsAppThread
from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.crud import whatsapp as whatsapp_crud
from app.crud import flow as flow_crud
from app.service.flow_executor import execute_flow
from app.schemas.whatsapp import WhatsAppUserUpdate, SendMessageRequest
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from datetime import datetime
from uuid import UUID
from app.schemas.whatsapp import WhatsAppMessageBase
from app.database import get_db
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

load_dotenv()
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
    
    Args:
        request: FastAPI request object
        form_data: Dictionary of form data from the request
        
    Returns:
        bool: True if signature is valid or validation is disabled, False otherwise
    """
    # Skip validation in development/staging if configured
    skip_validation = os.getenv("SKIP_TWILIO_VALIDATION", "False").lower() == "true"
    if skip_validation:
        print("Warning: Twilio signature validation is disabled")
        return True
    
    if not auth_token:
        print("Warning: TWILIO_AUTH_TOKEN not set, cannot validate signature")
        return False
    
    validator = RequestValidator(auth_token)
    
    # Get the signature from headers
    signature = request.headers.get("X-Twilio-Signature", "")
    
    # Get the full URL
    url = str(request.url)
    
    # Validate the request
    is_valid = validator.validate(url, form_data, signature)
    
    if not is_valid:
        print(f"Invalid Twilio signature for URL: {url}")
    
    return is_valid


@router.post(
    "/send",
    response_class=PlainTextResponse,
    summary="Handle outbound WhatsApp messages",
    operation_id="send",
)
async def whatsapp_send(request: Request, to_number: str, from_number: str, body: str):
    """
    Send a WhatsApp message using Twilio.

    Args:
        request (Request): The FastAPI request object.
        to_number (str): The recipient's phone number in E.164 format.
        from_number (str): The sender's Twilio WhatsApp number in E.164 format.
        body (str): The content of the message.

    Returns:
        JSONResponse: A JSON object containing the message SID, status, and body.
    """
    message = send_whatsapp_message(to_number, from_number, body)
    return JSONResponse(
        content={
            "sid": message.sid,
            "status": message.status,
            "body": message.body,
        }
    )


@router.post(
    "/receive",
    response_class=PlainTextResponse,
    summary="Handle incoming WhatsApp messages",
    operation_id="receive",
)
async def whatsapp_receive(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Handle incoming WhatsApp messages from Twilio.

    Args:
        request (Request): The FastAPI request object.
        From (str): The sender's phone number (provided by Twilio).
        Body (str): The content of the received message.

    Returns:
        PlainTextResponse: An XML response containing a thank you message.
    """
    # Get form data for signature validation
    form = await request.form()
    form_data = dict(form)
    
    # Validate Twilio signature
    if not validate_twilio_request(request, form_data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature"
        )
    
    print(f"Received message from {From}: {Body}")

    # Return proper TwiML response
    response = MessagingResponse()
    response.message("Thanks for your message! We'll get back to you shortly.")

    return PlainTextResponse(content=str(response), media_type="application/xml")


@router.post(
    "/receive-agent",
    response_class=PlainTextResponse,
    summary="Handle incoming WhatsApp messages using the WhatsApp agent",
    operation_id="receive_agent",
)
async def whatsapp_receive_with_agent(
    request: Request,
    db: Session = Depends(get_db),
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    ProfileName: str = Form(None),
    WaId: str = Form(None),
    NumMedia: int = Form(0),
):
    """
    Handle incoming WhatsApp messages from Twilio using the WhatsApp agent.

    Args:
        request (Request): The FastAPI request object.
        From (str): The sender's phone number (provided by Twilio).
        Body (str): The content of the received message.

    Returns:
        PlainTextResponse: An XML response containing the agent's reply message.
    """
    form = await request.form()
    form_data = dict(form)
    
    # Validate Twilio signature
    if not validate_twilio_request(request, form_data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature"
        )

    try:
        message_data = WhatsAppMessageBase(**form_data)
        print(f"Parsed message data: {message_data}")
    except Exception as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    to_number = message_data.To.replace("whatsapp:", "")  # This is your Twilio number
    from_number = message_data.From.replace(
        "whatsapp:", ""
    )  # This is the user's number

    # Look up organization by phone number
    organization = (
        db.query(Organization)
        .filter(Organization.phone_number == str(to_number))
        .first()
    )

    # Staging mode for Twilio sandbox testing
    STAGING_MODE = os.getenv("WHATSAPP_STAGING_MODE", "False").lower() == "true"
    STAGING_ORG_ID = os.getenv("WHATSAPP_STAGING_ORG_ID")

    if STAGING_MODE and not organization and STAGING_ORG_ID:
        # Use a predefined organization for staging/testing
        try:
            from uuid import UUID

            staging_org_id = UUID(STAGING_ORG_ID)
            organization = (
                db.query(Organization).filter(Organization.id == staging_org_id).first()
            )
            print(
                f"Using staging organization: {organization.name} (ID: {organization.id})"
            )
        except (ValueError, TypeError) as e:
            print(f"Error parsing staging organization ID: {e}")

    print("organization id:", organization.id)
    if not organization:
        raise HTTPException(status_code=400, detail="Unknown organization")
    
    # Find phone number record (supports multiple numbers per organization)
    phone_number_record = db.query(WhatsAppPhoneNumber).filter(
        WhatsAppPhoneNumber.phone_number == to_number
    ).first()
    
    # Determine which credentials to use
    if phone_number_record:
        # Use subaccount credentials from phone number's account
        org_account_sid = phone_number_record.account.twilio_subaccount_sid
        org_auth_token = decrypt_token(phone_number_record.account.twilio_auth_token)
        print(f"Using subaccount {org_account_sid} for {organization.name} via {phone_number_record.code}")
    else:
        # Fallback to main account for backward compatibility
        org_account_sid = account_sid
        org_auth_token = auth_token
        print(f"Using main account for organization {organization.name} (legacy mode)")

    whatsapp_dict = {}
    for key, value in form.items():
        whatsapp_dict[key] = value

    user = (
        db.query(WhatsAppUser)
        .filter(
            WhatsAppUser.phone_number == from_number,
            WhatsAppUser.organization_id == organization.id,
        )
        .first()
    )
    print(f"Found user: {user}")

    if not user:
        user = WhatsAppUser(
            phone_number=from_number,
            organization_id=organization.id,
            profile_name=message_data.ProfileName,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Find or create thread for this user
    thread = (
        db.query(WhatsAppThread)
        .filter(
            WhatsAppThread.user_id == user.id,
            WhatsAppThread.organization_id == organization.id,
        )
        .first()
    )

    if not thread:
        thread = WhatsAppThread(
            user_id=user.id,
            organization_id=organization.id,
            topic=f"Conversation with {user.profile_name or user.phone_number}",
            is_active=True,
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)

    # media = []

    # for i in range(NumMedia):
    #     media_url = form.get(f"MediaUrl{i}")
    #     media_type = form.get(f"MediaContentType{i}")
    #     if media_url:
    #         media.append({"url": media_url, "type": media_type})

    message = WhatsAppMessage(
        user_id=user.id,
        thread_id=thread.id,
        content=Body,
        direction="inbound",
        timestamp=datetime.now().isoformat(),
        message_sid=MessageSid,
        wa_id=WaId,
        profile_name=ProfileName,
        message_type=whatsapp_dict["MessageType"],
        num_segments=whatsapp_dict["NumSegments"],
        num_media=NumMedia,
        # media=media,
    )
    db.add(message)
    
    # Update thread timestamp
    thread.updated_at = datetime.now()
    
    db.commit()
    db.refresh(message)

    # Check if there's a matching flow for this message
    matched_flow = flow_crud.match_flow_trigger(db, organization.id, Body)
    
    if matched_flow:
        print(f"Matched flow: {matched_flow.code} - {matched_flow.name}")
        
        # Execute the flow
        flow_response = execute_flow(matched_flow, Body, from_number)
        
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
                user_id=user.id,
                thread_id=thread.id,
                content=flow_response,
                direction="outbound",
                role=WhatsAppMessage.ROLE["AGENT"],
                timestamp=datetime.now().isoformat(),
            )
            db.add(response_message)
            db.commit()
            
            # Return empty TwiML (message already sent)
            response = MessagingResponse()
            return PlainTextResponse(content=str(response), media_type="application/xml")
    
    # No flow matched, use the agent workflow
    print("No flow matched, using agent workflow")
    
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
        user_input=Body, whatsapp_message_id=message.id, user_phone_number=from_number
    )

    final_message = agent_result.get("final_message", "I'm processing your request...")

    response = MessagingResponse()
    
    return PlainTextResponse(content=str(response), media_type="application/xml")


@router.patch(
    "/users/{whatsapp_user_id}/organization",
    summary="Update a WhatsApp user's organization",
    response_model=dict,
)
async def update_whatsapp_user_organization_endpoint(
    whatsapp_user_id: UUID,
    user_update: WhatsAppUserUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a WhatsApp user's organization

    Args:
        whatsapp_user_id: The ID of the WhatsApp user to update
        user_update: The update data containing the new organization ID
        db: Database session

    Returns:
        Updated WhatsApp user information
    """
    # Update the user's organization
    updated_user = whatsapp_crud.update_whatsapp_user_organization(
        db=db, user_id=whatsapp_user_id, organization_id=user_update.organization_id
    )

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WhatsApp user not found or organization does not exist",
        )

    # Return the updated user information
    return {
        "id": str(updated_user.id),
        "phone_number": updated_user.phone_number,
        "organization_id": str(updated_user.organization_id),
        "profile_name": updated_user.profile_name,
        "message": "WhatsApp user organization updated successfully",
    }


@router.get(
    "/threads",
    summary="Get all threads for an organization",
    response_model=list,
)
async def get_threads(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all WhatsApp threads for an organization
    """
    threads = whatsapp_crud.get_threads_by_organization(db, organization_id)
    
    result = []
    for thread in threads:
        # Get user info
        user = thread.user
        # Get last message
        last_message = None
        if thread.messages:
            last_message = thread.messages[-1].content if thread.messages else None
        
        result.append({
            "id": str(thread.id),
            "code": thread.code,
            "user_id": str(thread.user_id),
            "organization_id": str(thread.organization_id),
            "topic": thread.topic,
            "is_active": thread.is_active,
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
            "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
            "phone_number": user.phone_number if user else None,
            "profile_name": user.profile_name if user else None,
            "last_message": last_message,
        })
    
    return result


@router.get(
    "/threads/{thread_id}/messages",
    summary="Get all messages for a thread",
    response_model=list,
)
async def get_thread_messages(
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all messages for a specific WhatsApp thread
    """
    messages = whatsapp_crud.get_thread_messages(db, thread_id)
    
    return [
        {
            "id": str(msg.id),
            "code": msg.code,
            "user_id": str(msg.user_id),
            "thread_id": str(msg.thread_id) if msg.thread_id else None,
            "direction": msg.direction,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "message_sid": msg.message_sid,
            "profile_name": msg.profile_name,
        }
        for msg in messages
    ]


@router.get(
    "/users",
    summary="Get all WhatsApp users for an organization",
    response_model=list,
)
async def get_whatsapp_users(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all WhatsApp users for an organization
    """
    users = whatsapp_crud.get_whatsapp_users_by_organization(db, organization_id)
    
    return [
        {
            "id": str(user.id),
            "code": user.code,
            "phone_number": user.phone_number,
            "profile_name": user.profile_name,
            "organization_id": str(user.organization_id),
        }
        for user in users
    ]


@router.get(
    "/stats",
    summary="Get WhatsApp statistics for an organization",
    response_model=dict,
)
async def get_stats(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get statistics for an organization's WhatsApp activity
    """
    stats = whatsapp_crud.get_organization_stats(db, organization_id)
    return stats


@router.get(
    "/recent-messages",
    summary="Get recent messages for an organization",
    response_model=list,
)
async def get_recent_messages(
    organization_id: UUID,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent messages for an organization
    """
    messages = whatsapp_crud.get_recent_messages(db, organization_id, limit)
    
    return [
        {
            "id": str(msg.id),
            "code": msg.code,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "direction": msg.direction,
            "sender": msg.user.profile_name or msg.user.phone_number if msg.user else "Unknown",
            "preview": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
        }
        for msg in messages
    ]


@router.post(
    "/threads/{thread_id}/send",
    summary="Send a WhatsApp message via thread",
    response_model=dict,
)
async def send_message_via_thread(
    thread_id: UUID,
    message_request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a WhatsApp message to a user via their thread.
    
    This endpoint:
    - Validates auth and org access
    - Determines from_number from Organization.phone_number
    - Resolves to_number from the thread's user.phone_number
    - Sends via Twilio and persists an outbound WhatsAppMessage
    - Updates WhatsAppThread.updated_at
    """
    # Get the thread
    thread = db.query(WhatsAppThread).filter(WhatsAppThread.id == thread_id).first()
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )
    
    # Verify user has access to this thread's organization
    if str(current_user.organization_id) != str(thread.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this thread"
        )
    
    # Get the organization to determine from_number
    organization = db.query(Organization).filter(
        Organization.id == thread.organization_id
    ).first()
    
    if not organization or not organization.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization phone number not configured"
        )
    
    # Get the user to determine to_number
    user = db.query(WhatsAppUser).filter(WhatsAppUser.id == thread.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for this thread"
        )
    
    from_number = organization.phone_number
    to_number = user.phone_number
    
    # Initialize Twilio client
    twilio_client = Client(account_sid, auth_token)
    
    try:
        # Send message via Twilio
        twilio_message = twilio_client.messages.create(
            body=message_request.body,
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
        )
        
        # Persist outbound message to database
        outbound_message = WhatsAppMessage(
            user_id=user.id,
            thread_id=thread.id,
            content=message_request.body,
            direction="outbound",
            role=WhatsAppMessage.ROLE["AGENT"],
            timestamp=datetime.now().isoformat(),
            message_sid=twilio_message.sid,
            sms_status=twilio_message.status,
        )
        db.add(outbound_message)
        
        # Update thread timestamp
        thread.updated_at = datetime.now()
        
        db.commit()
        db.refresh(outbound_message)
        
        return {
            "id": str(outbound_message.id),
            "code": outbound_message.code,
            "message_sid": twilio_message.sid,
            "status": twilio_message.status,
            "content": message_request.body,
            "timestamp": outbound_message.timestamp,
            "thread_id": str(thread_id),
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )
