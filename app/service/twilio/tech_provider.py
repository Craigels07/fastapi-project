"""
Twilio Tech Provider Service
Handles Twilio subaccount creation and WhatsApp sender registration
for the WhatsApp Tech Provider Program integration.
"""

import os
from typing import Dict, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


class TwilioTechProviderService:
    """Service for managing Twilio subaccounts and WhatsApp senders"""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not self.account_sid or not self.auth_token:
            raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in environment")
        
        self.client = Client(self.account_sid, self.auth_token)

    async def create_subaccount(self, customer_name: str) -> Dict[str, str]:
        """
        Create a Twilio subaccount for a customer.
        
        Args:
            customer_name: Friendly name for the subaccount
            
        Returns:
            Dictionary containing account_sid, auth_token, friendly_name, and status
            
        Raises:
            TwilioRestException: If subaccount creation fails
        """
        try:
            subaccount = self.client.api.accounts.create(
                friendly_name=customer_name
            )
            
            return {
                "account_sid": subaccount.sid,
                "auth_token": subaccount.auth_token,
                "friendly_name": subaccount.friendly_name,
                "status": subaccount.status
            }
        except TwilioRestException as e:
            raise Exception(f"Failed to create Twilio subaccount: {e.msg}")

    async def register_whatsapp_sender(
        self,
        subaccount_sid: str,
        subaccount_token: str,
        phone_number: str,
        waba_id: str,
        display_name: str,
        callback_url: str,
        status_callback_url: str,
        fallback_url: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Register a WhatsApp sender using the Twilio Senders API.
        
        Args:
            subaccount_sid: Twilio subaccount SID
            subaccount_token: Twilio subaccount auth token
            phone_number: Phone number in E.164 format (e.g., +1234567890)
            waba_id: WhatsApp Business Account ID from Meta
            display_name: Display name for the WhatsApp profile
            callback_url: URL for inbound message webhooks
            status_callback_url: URL for message status webhooks
            fallback_url: Optional fallback URL
            
        Returns:
            Dictionary containing sender_sid, sender_id, and status
            
        Raises:
            TwilioRestException: If sender registration fails
        """
        try:
            # Create client with subaccount credentials
            sub_client = Client(subaccount_sid, subaccount_token)
            
            # Format sender_id as whatsapp:+1234567890
            sender_id = f"whatsapp:{phone_number}"
            
            # Prepare configuration
            configuration = {
                "callback_url": callback_url,
                "callback_method": "POST",
                "status_callback_url": status_callback_url,
                "profile": {
                    "name": display_name
                }
            }
            
            # Add WABA ID if this is the first sender for this subaccount
            if waba_id:
                configuration["waba_id"] = waba_id
            
            # Add fallback URL if provided
            if fallback_url:
                configuration["fallback_url"] = fallback_url
                configuration["fallback_method"] = "POST"
            
            # Create the sender
            sender = sub_client.messaging.v2.channels.senders.create(
                sender_id=sender_id,
                configuration=configuration
            )
            
            return {
                "sender_sid": sender.sid,
                "sender_id": sender.sender_id,
                "status": sender.status,
                "messaging_service_sid": getattr(sender, "messaging_service_sid", None)
            }
        except TwilioRestException as e:
            raise Exception(f"Failed to register WhatsApp sender: {e.msg}")

    async def get_sender_status(
        self,
        subaccount_sid: str,
        subaccount_token: str,
        sender_sid: str
    ) -> Dict[str, str]:
        """
        Check the status of a WhatsApp sender registration.
        
        Args:
            subaccount_sid: Twilio subaccount SID
            subaccount_token: Twilio subaccount auth token
            sender_sid: Sender SID to check
            
        Returns:
            Dictionary containing status and sender_id
            
        Raises:
            TwilioRestException: If status check fails
        """
        try:
            sub_client = Client(subaccount_sid, subaccount_token)
            sender = sub_client.messaging.v2.channels.senders(sender_sid).fetch()
            
            return {
                "status": sender.status,
                "sender_id": sender.sender_id
            }
        except TwilioRestException as e:
            raise Exception(f"Failed to get sender status: {e.msg}")

    async def delete_sender(
        self,
        subaccount_sid: str,
        subaccount_token: str,
        sender_sid: str
    ) -> bool:
        """
        Delete a WhatsApp sender.
        
        Args:
            subaccount_sid: Twilio subaccount SID
            subaccount_token: Twilio subaccount auth token
            sender_sid: Sender SID to delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            TwilioRestException: If deletion fails
        """
        try:
            sub_client = Client(subaccount_sid, subaccount_token)
            sub_client.messaging.v2.channels.senders(sender_sid).delete()
            return True
        except TwilioRestException as e:
            raise Exception(f"Failed to delete sender: {e.msg}")

    async def suspend_subaccount(self, subaccount_sid: str) -> Dict[str, str]:
        """
        Suspend a Twilio subaccount.
        
        Args:
            subaccount_sid: Subaccount SID to suspend
            
        Returns:
            Dictionary containing account status
            
        Raises:
            TwilioRestException: If suspension fails
        """
        try:
            account = self.client.api.accounts(subaccount_sid).update(
                status="suspended"
            )
            
            return {
                "account_sid": account.sid,
                "status": account.status
            }
        except TwilioRestException as e:
            raise Exception(f"Failed to suspend subaccount: {e.msg}")

    async def reactivate_subaccount(self, subaccount_sid: str) -> Dict[str, str]:
        """
        Reactivate a suspended Twilio subaccount.
        
        Args:
            subaccount_sid: Subaccount SID to reactivate
            
        Returns:
            Dictionary containing account status
            
        Raises:
            TwilioRestException: If reactivation fails
        """
        try:
            account = self.client.api.accounts(subaccount_sid).update(
                status="active"
            )
            
            return {
                "account_sid": account.sid,
                "status": account.status
            }
        except TwilioRestException as e:
            raise Exception(f"Failed to reactivate subaccount: {e.msg}")

    async def list_senders(
        self,
        subaccount_sid: str,
        subaccount_token: str
    ) -> list:
        """
        List all WhatsApp senders registered to a subaccount.
        
        Args:
            subaccount_sid: Twilio subaccount SID
            subaccount_token: Twilio subaccount auth token
            
        Returns:
            List of dictionaries containing sender information
            
        Raises:
            TwilioRestException: If listing fails
        """
        try:
            sub_client = Client(subaccount_sid, subaccount_token)
            senders = sub_client.messaging.v2.channels.senders.list()
            
            return [
                {
                    "sender_sid": sender.sid,
                    "sender_id": sender.sender_id,
                    "status": sender.status,
                    "messaging_service_sid": getattr(sender, "messaging_service_sid", None)
                }
                for sender in senders
            ]
        except TwilioRestException as e:
            raise Exception(f"Failed to list senders: {e.msg}")

    async def update_sender(
        self,
        subaccount_sid: str,
        subaccount_token: str,
        sender_sid: str,
        callback_url: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Update a WhatsApp sender's configuration.
        
        Args:
            subaccount_sid: Twilio subaccount SID
            subaccount_token: Twilio subaccount auth token
            sender_sid: Sender SID to update
            callback_url: Optional new callback URL for inbound messages
            status_callback_url: Optional new status callback URL
            display_name: Optional new display name
            
        Returns:
            Dictionary containing updated sender information
            
        Raises:
            TwilioRestException: If update fails
        """
        try:
            sub_client = Client(subaccount_sid, subaccount_token)
            
            # Build configuration update
            configuration = {}
            if callback_url:
                configuration["callback_url"] = callback_url
                configuration["callback_method"] = "POST"
            if status_callback_url:
                configuration["status_callback_url"] = status_callback_url
            if display_name:
                configuration["profile"] = {"name": display_name}
            
            # Update the sender
            sender = sub_client.messaging.v2.channels.senders(sender_sid).update(
                configuration=configuration
            )
            
            return {
                "sender_sid": sender.sid,
                "sender_id": sender.sender_id,
                "status": sender.status
            }
        except TwilioRestException as e:
            raise Exception(f"Failed to update sender: {e.msg}")
