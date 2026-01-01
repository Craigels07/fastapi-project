"""
Flow execution service for processing flows triggered by incoming messages.
"""
from typing import Dict, Any, Optional
from app.models.flow import Flow
from app.models.whatsapp import WhatsAppUser, WhatsAppThread
from app.helpers.compliance_helper import can_send_freeform_message, enforce_opt_out
from twilio.rest import Client
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Initialize Twilio client
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None


class FlowExecutor:
    """
    Executes flows based on their node configuration.
    This is a simple implementation that processes trigger and response nodes.
    """

    def __init__(self, flow: Flow, organization_phone: str = None, db_session=None, thread: WhatsAppThread = None, user: WhatsAppUser = None):
        self.flow = flow
        self.nodes = {node["id"]: node for node in flow.nodes}
        self.edges = flow.edges
        self.organization_phone = organization_phone
        self.db_session = db_session
        self.thread = thread
        self.user = user

    def execute(self, context: Dict[str, Any], send_whatsapp: bool = False) -> Optional[str]:
        """
        Execute the flow and return the response message.
        
        Args:
            context: Dictionary containing execution context (user_input, user_phone, etc.)
            
        Returns:
            Response message string or None
        """
        # Find the trigger node (entry point)
        trigger_node = self._find_trigger_node()
        if not trigger_node:
            print(f"No trigger node found in flow {self.flow.code}")
            return None

        # Start execution from trigger node
        current_node_id = trigger_node["id"]
        
        # Simple execution: follow edges to find response nodes
        visited = set()
        max_iterations = 20  # Prevent infinite loops
        iteration = 0
        
        while current_node_id and iteration < max_iterations:
            iteration += 1
            
            if current_node_id in visited:
                break
            visited.add(current_node_id)
            
            current_node = self.nodes.get(current_node_id)
            if not current_node:
                break
            
            # If we hit a send-message or response node, process and optionally send it
            node_type = current_node.get("data", {}).get("nodeType") or current_node.get("type")
            if node_type in ["send-message", "response"]:
                message_result = self._process_send_message_node(current_node, context, send_whatsapp)
                return message_result.get("message")
            
            # Move to next node
            next_edges = [e for e in self.edges if e["source"] == current_node_id]
            if next_edges:
                current_node_id = next_edges[0]["target"]
            else:
                break
        
        return None

    def _find_trigger_node(self) -> Optional[Dict[str, Any]]:
        """Find the trigger node in the flow"""
        for node in self.flow.nodes:
            node_type = node.get("data", {}).get("nodeType") or node.get("type")
            if node_type and node_type.startswith("trigger"):
                return node
        return None

    def _process_send_message_node(
        self, node: Dict[str, Any], context: Dict[str, Any], send_whatsapp: bool = False
    ) -> Dict[str, Any]:
        """
        Process a send-message node with full WhatsApp features.
        Supports: message body, buttons, delay, template variables.
        CRITICAL: Enforces compliance checks before sending.
        """
        data = node.get("data", {})
        message = data.get("message", "")
        buttons = data.get("buttons", [])
        delay = data.get("delay", 0)
        
        # Replace template variables
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        
        # Apply delay if specified
        if delay > 0:
            print(f"Waiting {delay} seconds before sending message...")
            time.sleep(delay)
        
        # Send WhatsApp message if enabled
        if send_whatsapp and message and twilio_client:
            user_phone = context.get("user_phone")
            org_phone = self.organization_phone
            
            if user_phone and org_phone:
                try:
                    # CRITICAL: Enforce compliance checks before sending
                    if self.user and self.thread:
                        # Check opt-out status
                        if self.user.opted_out:
                            print(f"COMPLIANCE BLOCK: User {user_phone} is opted out. Message not sent.")
                            return {
                                "message": message,
                                "buttons": buttons,
                                "delay": delay,
                                "blocked": True,
                                "reason": "user_opted_out"
                            }
                        
                        # Check 24-hour window for freeform messages
                        if not can_send_freeform_message(self.thread):
                            print(f"COMPLIANCE BLOCK: 24-hour window expired for {user_phone}. Message not sent.")
                            print(f"TIP: Use a template message instead, or wait for user to message first.")
                            return {
                                "message": message,
                                "buttons": buttons,
                                "delay": delay,
                                "blocked": True,
                                "reason": "24h_window_expired"
                            }
                    
                    # Handle development environment
                    if os.getenv("ENVIRONMENT") in ["development", "staging"]:
                        dev_phone = os.getenv("DEV_WHATSAPP_NUMBER")
                        if dev_phone:
                            user_phone = dev_phone
                    
                    # Format message with buttons if present
                    final_message = message
                    if buttons and len(buttons) > 0:
                        # Add buttons as numbered options (WhatsApp doesn't support interactive buttons via Twilio API)
                        final_message += "\n\n"
                        for i, button in enumerate(buttons[:3], 1):  # Max 3 buttons
                            button_text = button.get("text", "")
                            if button_text:
                                final_message += f"{i}. {button_text}\n"
                    
                    # Send the message via Twilio
                    twilio_client.messages.create(
                        body=final_message,
                        from_=f"whatsapp:{org_phone}",
                        to=f"whatsapp:{user_phone}" if not user_phone.startswith("whatsapp:") else user_phone
                    )
                    print(f"WhatsApp message sent to {user_phone}: {final_message[:50]}...")
                except Exception as e:
                    print(f"Error sending WhatsApp message: {e}")
        
        return {
            "message": message,
            "buttons": buttons,
            "delay": delay
        }


def execute_flow(
    flow: Flow, 
    user_input: str, 
    user_phone: str,
    organization_phone: str = None,
    send_whatsapp: bool = False
) -> Optional[str]:
    """
    Convenience function to execute a flow.
    
    Args:
        flow: The Flow model to execute
        user_input: The user's message text
        user_phone: The user's phone number
        organization_phone: The organization's WhatsApp number (for sending)
        send_whatsapp: Whether to actually send WhatsApp messages via Twilio
        
    Returns:
        Response message or None
    """
    executor = FlowExecutor(flow, organization_phone)
    context = {
        "user_input": user_input,
        "user_phone": user_phone,
        "message": user_input,
    }
    return executor.execute(context, send_whatsapp=send_whatsapp)
