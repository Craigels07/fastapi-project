from fastapi import APIRouter, Request, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from app.helpers.whatsapp_helper import send_whatsapp_message
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


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
    response.message("Thanks for your message! We’ll get back to you shortly CRAIG.")

    return PlainTextResponse(content=str(response), media_type="application/xml")
