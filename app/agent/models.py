
from langgraph.graph import MessagesState
from typing import Optional

class MessageState(MessagesState):
    summary: Optional[str] = None