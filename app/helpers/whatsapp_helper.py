"""Helper to send WhatsApp messages."""

import os
from twilio.rest import Client  # type: ignore
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)  # type: ignore


def send_whatsapp_message(to_number: str, from_number: str, body: str):
    """
    Send a WhatsApp message using Twilio.

    Args:
        to_number (str): The recipient's phone number.
        from_number (str): The sender's Twilio WhatsApp number.
        body (str): The content of the message.

    Returns:
        twilio.rest.api.v2010.account.message.MessageInstance: The sent message object.

    Raises:
        twilio.base.exceptions.TwilioRestException: If there's an error sending the message.

    Note:
        Both 'to_number' and 'from_number' should be in E.164 format without the 'whatsapp:' prefix.
    """
    message = client.messages.create(
        body=body,
        from_=f"whatsapp:{from_number}",
        to=f"whatsapp:{to_number}",
    )

    print(message.body)
    return message
