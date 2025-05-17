"""Helper to send WhatsApp messages."""

import os
from twilio.rest import Client  # type: ignore
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from app.helpers.collection_helpers import get_or_create_collection
from app.database import SessionLocal
from typing import Dict, Any, List
from app.schemas.document import SearchResponse
from datetime import datetime

# Models:
from app.agent.models import MessageState
from models.whatsapp import WhatsAppUser, WhatsAppMessage
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
import json
from sqlalchemy.orm import Session

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)  # type: ignore

# Optional Node
def call_model(state: MessageState, config: Dict[str, Any]):
    """Call the model with the current state of the conversation."""

    model = config["configurable"]["model"]

    summary = state.get("summary", "")

    if summary:
        system_message = f"Summary of conversation earlier: {summary}"
        messages = [SystemMessage(content=system_message)] + state["messages"]
    else:
        messages = state["messages"]

    response = model.invoke(messages)

    return {"messages": response, "summary": summary}

# Optional Node
def should_continue(state: MessageState, config: Dict[str, Any]):
    """Return the next node to execute."""

    messages = state["messages"]

    # If there are more than six messages, then we summarize the conversation
    if len(messages) > 6:
        return "summarize_conversation"

    # Determine whether to end or summarize the conversation
    return END


# Tool
def search_documents(query: str, limit: int = 5) -> List[SearchResponse]:
    """
    Search the user's document collection for relevant documents using semantic similarity.

    Args:
        query (str): The user's search query or question.
        limit (int, optional): The maximum number of relevant documents to return. Defaults to 5.

    Returns:
        List[SearchResponse]: A list of documents most relevant to the query.

    When to use:
        Use this tool whenever you need to retrieve information from the user's documents to answer a question or provide context.
        For example, if the user asks about the content of a document, requests a summary, or asks a factual question that may be answered by stored documents.

    Example usage:
        search_documents("What are the terms of the contract with ACME Corp?")
    """
    responses = []
    with SessionLocal() as db:
        collection = get_or_create_collection(db, "craig_test")

        embeddings = OpenAIEmbeddings(
            api_key=OPENAI_API_KEY, model="text-embedding-3-small"
        )

        vectorstore = PGVector(
            connection=DATABASE_URL,
            collection_name=collection.name,
            embeddings=embeddings,
            use_jsonb=True,
        )
    results = vectorstore.similarity_search(query, k=limit)

    for result in results:
        responses.append(
            SearchResponse(
                id=result.metadata.get("document_id") or result.metadata.get("id"),
                filename=result.metadata.get("filename"),
                preview=result.metadata.get("preview", ""),
                collection_id=result.metadata.get("collection_id") or 0,
                similarity=result.metadata.get("similarity", 1.0),
            )
        )

    return responses

# Tool or Node? How important is stepping into woo_commerce orders - there might also be other services to come.
def fetch_order_info():
    # [Tools Node (multi-tool router)]
    # ├── Order Info Tool (API call to internal DB or order service)
    pass

# Tool or Node?
def escalate_to_human():
    # [Tools Node (multi-tool router)]
    # ├── Human Escalation Tool (if needed)
    pass

# Tool
def log_internal_notes():
    # [Tools Node (multi-tool router)]
    # ├── Internal Notes Tool (to write back to CRM/logs)
    pass


# Nodes


async def receive_message(state: dict) -> dict:
    user_input = state.get("user_input")
    user_phone = state.get("user_phone")

    # Open a DB session
    session = SessionLocal()

    try:
        # Find or create the WhatsAppUser by phone
        user = session.query(WhatsAppUser).filter_by(phone_number=user_phone).first()
        if not user:
            user = WhatsAppUser(phone_number=user_phone)
            session.add(user)
            session.commit()  # Commit to generate user.id

        # Create a new WhatsAppMessage entry
        message = WhatsAppMessage(
            user_id=user.id,
            direction="inbound",
            content=user_input,
            timestamp=datetime.utcnow().isoformat(),
            message_metadata=None,  # add metadata if any
        )
        session.add(message)
        session.commit()

    except Exception as e:
        print(f"Error saving WhatsApp message: {e}")
        session.rollback()

    finally:
        session.close()

    # Return updated state for next node
    return {
        **state,
        "received_message": user_input,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def parse_intent(state: dict) -> dict:
    message = state.get("received_message")
    if not message:
        return {**state, "intent": None, "entities": {}}

    # Define expected output schema
    response_schemas = [
        ResponseSchema(
            name="intent",
            description="Intent of the user message, e.g. greeting, order_query, complaint, info_request, unknown",
        ),
        ResponseSchema(
            name="entities",
            description="Dictionary of relevant entities extracted from the message, like order_id, product_name, dates",
        ),
    ]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = output_parser.get_format_instructions()

    # Build prompt messages
    system_message = SystemMessage(
        content="You are a helpful assistant that extracts intent and entities from user messages."
    )
    human_message = HumanMessage(content=f"Message: {message}\n\n{format_instructions}")

    # Initialize chat model
    chat = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

    # Call the model
    response = await chat.agenerate([[system_message, human_message]])

    # Parse output
    try:
        parsed = output_parser.parse(response.generations[0][0].text)
        intent = parsed.get("intent")
        entities = parsed.get("entities", {})
    except json.JSONDecodeError:
        intent = None
        entities = {}

    return {**state, "intent": intent, "entities": entities}


def retrieve_conversation_context(state: dict, session: Session) -> dict:
    """
    Retrieve recent conversation history for the user to add context.

    Args:
        state (dict): Current state containing 'user_id'.
        session (Session): SQLAlchemy DB session.

    Returns:
        dict: Updated state including 'conversation_context' as a string or list.
    """

    user_id = state.get("user_id")
    if not user_id:
        # No user, no context
        return {**state, "conversation_context": []}

    # Query last 20 messages from the user, ordered newest first
    recent_msgs = (
        session.query(WhatsAppMessage)
        .filter(WhatsAppMessage.user_id == user_id)
        .order_by(WhatsAppMessage.timestamp.desc())
        .limit(20)
        .all()
    )

    # Format messages as strings or dicts for context
    # Example: [{'role': 'user', 'content': 'Hi'}, {'role': 'agent', 'content': 'Hello!'}]
    context = []
    for msg in reversed(recent_msgs):  # reverse to chronological order
        role = "user" if msg.direction == "inbound" else "agent"
        context.append({"role": role, "content": msg.content})

    # Optionally add context from LangChain Memory or RAG retrieval here
    # e.g., context.extend(rag_vectorstore.retrieve_relevant_docs(user_id))

    return {**state, "conversation_context": context}


async def run_agent_reasoning(state: Dict) -> Dict:
    """
    Reasoning node that:
    - Examines intent & entities
    - Uses tools/APIs if needed
    - Generates a reply for WhatsApp user

    Args:
        state (dict): Should contain keys like:
            - intent (str)
            - entities (dict)
            - conversation_context (list of dicts)
            - user_phone (str)

    Returns:
        dict: Updated state with "agent_response" key containing reply text.
    """
    intent = state.get("intent")
    entities = state.get("entities", {})
    context = state.get("conversation_context", [])
    user_phone = state.get("user_phone")

    chat = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

    # Compose system prompt with instructions
    system_prompt = (
        "You are a helpful WhatsApp customer support assistant. "
        "Based on the conversation and user's intent, decide how to respond. "
        "If the user requests order info, call the Order Info tool (simulate). "
        "If unclear, ask for clarification politely."
    )

    # Build conversation history for the model (system + past messages + user message)
    messages = [SystemMessage(content=system_prompt)]
    for msg in context:
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            # Agent message
            messages.append(SystemMessage(content=content))

    # Add current user message for clarity
    if state.get("received_message"):
        messages.append(HumanMessage(content=state["received_message"]))

    # Example tool call simulation
    response_text = ""
    if intent == "order_query" and "order_id" in entities:
        # Call your order info API/tool here
        order_id = entities["order_id"]
        # Simulate fetching order info
        order_info = f"Order {order_id} is being processed and will ship soon."
        response_text = f"I found your order info: {order_info}"
    elif intent == "greeting":
        response_text = "Hello! How can I help you today?"
    elif intent == "complaint":
        response_text = "I'm sorry to hear that. Can you please provide more details?"
    else:
        # Use model to generate a fallback response
        completion = await chat.agenerate([messages])
        response_text = completion.generations[0][0].text.strip()

    # Return updated state with the final response for WhatsApp
    return {**state, "agent_response": response_text}


def generate_response(state: dict) -> dict:
    """
    Constructs the final natural language reply message for WhatsApp.

    Args:
        state (dict): Should contain keys like:
            - agent_response (str): The reply generated by reasoning node
            - tool_output (dict or str, optional): Any data fetched from tools/APIs
            - user_name (str, optional): To personalize message

    Returns:
        dict: Updated state including 'final_message' with the full text reply.
    """

    agent_response = state.get("agent_response", "")
    tool_output = state.get("tool_output", None)
    user_name = state.get("user_name", "there")

    # Start building the message
    message = f"Hi {user_name},\n\n{agent_response}"

    # Append tool output if available and meaningful
    if tool_output:
        if isinstance(tool_output, dict):
            # Format dict nicely (simple key: value lines)
            tool_text = "\n".join(f"{k}: {v}" for k, v in tool_output.items())
            message += f"\n\nHere is the information you requested:\n{tool_text}"
        else:
            # Otherwise just append as string
            message += f"\n\n{tool_output}"

    # Optionally add a friendly closing line
    message += "\n\nIf you have more questions, just reply here!"

    return {**state, "final_message": message}


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


def get_tools():
    """Get the tools available to the agent."""
    return [search_documents, log_internal_notes, escalate_to_human]


def model_with_tools():
    """
    Return a model with tools bound.
    """
    tools = get_tools()
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    llm_with_tools = model.bind_tools(tools)
    return llm_with_tools
