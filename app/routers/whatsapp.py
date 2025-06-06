import os
from fastapi import APIRouter, Request, Form
from dotenv import load_dotenv
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from app.helpers.whatsapp_helper import send_whatsapp_message, model_with_tools
from fastapi.responses import JSONResponse
from app.agent.whatsapp_agent import WhatsAppAgent
from app.models.user import Organization
from app.models.whatsapp import WhatsAppUser, WhatsAppMessage
from app.crud.whatsapp import update_whatsapp_user_organization
from app.schemas.whatsapp import WhatsAppUserUpdate
from fastapi import Depends, HTTPException, status
from datetime import datetime
from uuid import UUID
from app.schemas.whatsapp import WhatsAppMessageBase
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

load_dotenv()
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")


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
    print(f"Received message from {From}: {Body}")

    response = MessagingResponse()
    response.message("Thanks for your message! We’ll get back to you shortly Craig.")

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
            account_sid=whatsapp_dict["AccountSid"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # media = []

    # for i in range(NumMedia):
    #     media_url = form.get(f"MediaUrl{i}")
    #     media_type = form.get(f"MediaContentType{i}")
    #     if media_url:
    #         media.append({"url": media_url, "type": media_type})

    message = WhatsAppMessage(
        user_id=user.id,
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
    db.commit()
    db.refresh(message)

    # Create a WhatsApp agent with tools
    llm_with_tools = model_with_tools()
    whatsapp_agent = WhatsAppAgent(
        account_sid,
        auth_token,
        model=llm_with_tools,
        organization_id=organization.id,
        to_number=to_number,
    )

    # Process the message through the agent workflow
    agent_result = await whatsapp_agent.run(
        user_input=Body, whatsapp_message_id=message.id, user_phone_number=from_number
    )

    # Extract the final message from the result
    # The final_message field should be set by the generate_response node
    final_message = agent_result.get("final_message", "I'm processing your request...")

    return PlainTextResponse(content=str(final_message), media_type="application/xml")


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
    updated_user = update_whatsapp_user_organization(
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
