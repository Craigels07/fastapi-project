from langgraph.graph import MessagesState
from typing import Optional


class MessageState(MessagesState):
    summary: Optional[str] = None


class WhatsAppMessageState(MessageState):
    received_message: str
    user_phone_number: str

    user_id: Optional[int] = None
    entity_phone_number: str

    messagePurpose: Optional[str] = None
    messageDetails: Optional[dict] = None

    conversation_context: Optional[list] = []
    agent_response: Optional[str] = []
    tool_output: Optional[str] = None

    final_message: str
