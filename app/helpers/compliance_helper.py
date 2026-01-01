"""
WhatsApp Compliance Helper
Enforces Meta's critical compliance requirements:
- 24-hour messaging window
- Opt-out management (STOP/START keywords)
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from app.models.whatsapp import WhatsAppUser, WhatsAppThread


def can_send_freeform_message(thread: WhatsAppThread) -> bool:
    """
    Check if we're within Meta's 24-hour messaging window.
    
    Args:
        thread: WhatsAppThread instance
        
    Returns:
        True if within 24-hour window, False otherwise
    """
    if not thread.last_user_message_at:
        return False
    
    time_since_last_message = datetime.utcnow() - thread.last_user_message_at
    return time_since_last_message < timedelta(hours=24)


def enforce_24h_window(thread: WhatsAppThread, message_type: str = "freeform") -> None:
    """
    Enforce Meta's 24-hour messaging window.
    HARD REQUIREMENT: Must be called before EVERY send.
    
    Args:
        thread: WhatsAppThread instance
        message_type: "freeform" or "template"
        
    Raises:
        Exception: If outside 24-hour window and trying to send freeform message
    """
    if message_type == "template":
        return
    
    if not thread.last_user_message_at:
        raise Exception(
            "No user message received. Cannot send freeform message. "
            "Use approved template instead."
        )
    
    hours_since_last_message = (
        datetime.utcnow() - thread.last_user_message_at
    ).total_seconds() / 3600
    
    if hours_since_last_message > 24:
        raise Exception(
            f"Outside 24-hour window ({hours_since_last_message:.1f} hours since last user message). "
            "Use approved template only."
        )


def enforce_opt_out(user: WhatsAppUser, message_body: str, db) -> Dict[str, Any]:
    """
    Enforce opt-out status and handle STOP/START keywords.
    HARD REQUIREMENT: Must be called FIRST in webhook handler.
    
    Args:
        user: WhatsAppUser instance
        message_body: Message content from user
        db: Database session
        
    Returns:
        Dictionary with action and halt flag:
            - {"action": "opt_out", "halt": True} - User opted out
            - {"action": "opt_in", "halt": False} - User opted in
            - {"action": "continue", "halt": False} - Continue processing
            
    Raises:
        Exception: If user is opted out and trying to process message
    """
    message_lower = message_body.strip().lower()
    
    # Handle STOP keyword
    if message_lower == "stop":
        user.opted_out = True
        user.opted_out_at = datetime.utcnow()
        db.commit()
        return {"action": "opt_out", "halt": True}
    
    # Handle START keyword
    if message_lower == "start":
        user.opted_out = False
        user.opted_out_at = None
        db.commit()
        return {"action": "opt_in", "halt": False}
    
    # Check if user is opted out
    if user.opted_out:
        raise Exception(
            "User has opted out. Cannot process message or send responses."
        )
    
    return {"action": "continue", "halt": False}


def get_window_status(thread: WhatsAppThread) -> Dict[str, Any]:
    """
    Get detailed status of the 24-hour messaging window.
    
    Args:
        thread: WhatsAppThread instance
        
    Returns:
        Dictionary containing:
            - within_window: bool
            - hours_remaining: float (or None if no user message)
            - can_send_freeform: bool
            - last_user_message_at: datetime (or None)
    """
    if not thread.last_user_message_at:
        return {
            "within_window": False,
            "hours_remaining": None,
            "can_send_freeform": False,
            "last_user_message_at": None
        }
    
    time_since_last = datetime.utcnow() - thread.last_user_message_at
    hours_since = time_since_last.total_seconds() / 3600
    within_window = hours_since < 24
    hours_remaining = max(0, 24 - hours_since) if within_window else 0
    
    return {
        "within_window": within_window,
        "hours_remaining": hours_remaining,
        "can_send_freeform": within_window,
        "last_user_message_at": thread.last_user_message_at
    }
