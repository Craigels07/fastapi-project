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
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.schemas.whatsapp import WhatsAppMessageBase
from app.database import get_db

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

    to_number = message_data.To.replace("whatsapp:", "")
    from_number = message_data.From.replace("whatsapp:", "")

    organization = (
        db.query(Organization)
        .filter(Organization.phone_number == str(from_number))
        .first()
    )
    if not organization:
        raise HTTPException(status_code=400, detail="Unknown organization")

    whatsapp_dict = {}
    for key, value in form.items():
        whatsapp_dict[key] = value

    user = (
        db.query(WhatsAppUser)
        .filter(
            WhatsAppUser.phone_number == to_number,
            WhatsAppUser.organization_id == organization.id,
        )
        .first()
    )

    if not user:
        user = WhatsAppUser(
            phone_number=to_number,
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
        account_sid, auth_token, model=llm_with_tools, organization_id=organization.id
    )

    # Process the message through the agent workflow
    agent_result = await whatsapp_agent.run(
        user_input=Body, whatsapp_message_id=message.id, user_phone_number=to_number
    )

    # Extract the final message from the result
    # The final_message field should be set by the generate_response node
    final_message = agent_result.get("final_message", "I'm processing your request...")

    return PlainTextResponse(content=str(final_message), media_type="application/xml")
