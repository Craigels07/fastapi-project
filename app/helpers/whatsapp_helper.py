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
from app.database import get_db
from sqlalchemy.orm import Session
from app.agent.models import WhatsAppMessageState
from app.models.whatsapp import WhatsAppUser, WhatsAppMessage
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
import json
from app.models.user import Organization
from app.service.base import ServiceRegistry
from app.models.service_credential import ServiceCredential

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)  # type: ignore


# Optional Node
def call_model(state: WhatsAppMessageState, config: Dict[str, Any]):
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
def should_continue(state: WhatsAppMessageState, config: Dict[str, Any]):
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


async def receive_message(state: WhatsAppMessageState) -> dict:
    received_message = state.get("received_message")
    user_phone_number = state.get("user_phone_number")
    timestamp = datetime.now().isoformat()

    db_generator = get_db()
    db: Session = next(db_generator)

    try:
        print(f"user_phone_number: {user_phone_number}")
        user = db.query(WhatsAppUser).filter_by(phone_number=user_phone_number).first()

        if not user:
            raise ValueError(f"User with number: {user_phone_number}, not found.")

        user_id = user.id

    except Exception as e:
        print(f"Error retrieving WhatsApp message: {e}")
        db.rollback()

    finally:
        db.close()

    # Return updated state for next node
    return {
        **state,
        "received_message": received_message,
        "user_id": user_id,
        "timestamp": timestamp,
    }


async def parse_intent(state: WhatsAppMessageState, config: Dict[str, Any]) -> dict:
    message = state.get("received_message")
    if not message:
        return {**state, "messagePurpose": None, "messageDetails": {}}

    # Define expected output schema
    response_schemas = [
        ResponseSchema(
            name="messagePurpose",
            description="Purpose of the user message, e.g. greeting, order query, complaint, info request, unknown",
        ),
        ResponseSchema(
            name="messageDetails",
            description="Details relevant to the message, like order ID, product name, dates",
        ),
    ]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = output_parser.get_format_instructions()

    # Build prompt messages
    system_message = SystemMessage(
        content="I need to understand the user's message to provide the right assistance. Please identify the purpose of the message and any specific details mentioned, such as order IDs, product names, or dates."
    )
    human_message = HumanMessage(content=f"Message: {message}\n\n{format_instructions}")

    model = config["configurable"]["model"]

    # Call the model
    response = await model.agenerate([[system_message, human_message]])

    # Parse output
    try:
        parsed = output_parser.parse(response.generations[0][0].text)
        messagePurpose = parsed.get("messagePurpose")
        messageDetails = parsed.get("messageDetails", {})
    except json.JSONDecodeError:
        # If there is a JSON parsing error, we keep the defaults
        pass

    return {**state, "messagePurpose": messagePurpose, "messageDetails": messageDetails}


def retrieve_conversation_context(
    state: WhatsAppMessageState, config: Dict[str, Any]
) -> dict:
    """
    Retrieve recent conversation history for the user to add context.

    Args:
        state (dict): Current state containing 'user_id'.

    Returns:
        dict: Updated state including 'conversation_context' as a string or list.
    """

    user_id = state.get("user_id")
    organization_id = config["configurable"]["organization_id"]
    print(f"User ID: {user_id}, Organization ID: {organization_id}")
    if not all([user_id, organization_id]):
        # No user, no context
        print("No user or organization found.")
        return {**state, "conversation_context": []}

    db_generator = get_db()
    db: Session = next(db_generator)

    try:
        # Query last 20 messages from the user, ordered newest first
        recent_msgs = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.user_id == user_id,
            )
            .order_by(WhatsAppMessage.timestamp.desc())
            .limit(20)
            .all()
        )
        print(f"Recent messages: {recent_msgs}")

        # Format messages as strings or dicts for context
        # Example: [{'role': 'user', 'content': 'Hi'}, {'role': 'agent', 'content': 'Hello!'}]
        context = []
        for msg in reversed(recent_msgs):  # reverse to chronological order
            role = "user" if msg.direction == "inbound" else "agent"
            context.append({"role": role, "content": msg.content})

        # Optionally add co ntext from LangChain Memory or RAG retrieval here
        # e.g., context.extend(rag_vectorstore.retrieve_relevant_docs(user_id))

        return {**state, "conversation_context": context}

    except Exception as e:
        print(f"Error retrieving conversation context: {e}")
        return {**state, "conversation_context": []}

    finally:
        db.close()


async def run_agent_reasoning(
    state: WhatsAppMessageState, config: Dict[str, Any]
) -> dict:
    """
    Reasoning node that:
    - Examines messagePurpose & messageDetails
    - Uses tools/APIs if needed
    - Generates a reply for WhatsApp user

    Args:
        state (dict): Should contain keys like:
            - messagePurpose (str)
            - messageDetails (dict)
            - conversation_context (list of dicts)
            - user_phone_number (str)

    Returns:
        dict: Updated state with "agent_response" key containing reply text.
    """
    print("Running agent reasoning...")
    messagePurpose = state.get("messagePurpose")
    messageDetails = state.get("messageDetails", {})
    context = state.get("conversation_context", [])
    user_phone_number = state.get("user_phone_number")
    organization_id = config["configurable"]["organization_id"]
    received_message = state.get("received_message", "")

    model = config["configurable"]["model"]

    # Compose system prompt with instructions
    system_prompt = (
        "You are a helpful WhatsApp customer support assistant. "
        "Based on the conversation and user's message purpose, decide how to respond. "
        "If the user requests order information, use the available tools to fetch it. "
        "Be concise, friendly, and helpful in your responses."
    )

    # Build conversation history for the model
    messages = [SystemMessage(content=system_prompt)]

    # Add conversation context if available
    if isinstance(context, list):
        for msg in context:
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                # Agent message
                messages.append(SystemMessage(content=content))

    # Add current user message
    messages.append(HumanMessage(content=received_message))

    response_text = ""
    tool_output = None

    try:
        # Open a database session
        db_generator = get_db()
        db: Session = next(db_generator)

        # Try to find the organization associated with the phone number
        organization = db.query(Organization).filter_by(id=organization_id).first()
        print(
            f"in run_agent_reasoning, organization id= {organization} for organization id {organization_id}"
        )

        # Get the list of available services for this organization
        organization_services = []

        if organization:
            print("Fetching organization services...")

            try:
                # Try to query service credentials, but handle case where table doesn't exist
                organization_services = list(
                    db.query(ServiceCredential).filter_by(
                        organization_id=organization_id
                    )
                )
                print(
                    f"Available services for organization {organization.id}: {organization_services}"
                )
            except Exception as e:
                # Handle case where table doesn't exist or other DB errors
                print(f"Error fetching service credentials: {e}")
                organization_services = []

        # Find a service that can handle this message purpose
        service = ServiceRegistry.find_capable_service(
            organization_services=organization_services,
            message_purpose=messagePurpose,
            message_details=messageDetails,
        )

        # If we found a capable service, let it process the request
        if service:
            result = service.process_request(messagePurpose, messageDetails)
            response_text = result.get("response_text", "")
            tool_output = result.get("tool_output")
        # Fall back to generic responses if no service can handle it
        elif messagePurpose == "order_query":
            response_text = "It looks like you're asking about an order, but I don't have access to your order information right now."
        elif messagePurpose == "get_product_info":
            response_text = "I'd like to help you find product information, but I don't have access to your product catalog right now."

        # elif messagePurpose == "greeting":
        #     response_text = (
        #         "Hello! How can I help you today with your order or product inquiries?"
        #     )

        # elif messagePurpose == "complaint":
        #     response_text = "I'm sorry to hear you're having an issue. Could you please provide more details about what happened so I can help resolve it?"

        # elif messagePurpose == "farewell":
        #     response_text = "Thank you for contacting us! If you have any more questions, feel free to message again. Have a great day!"

        else:
            # Use model to generate a fallback response when we can't categorize the message
            print("Generating fallback response...")
            completion = await model.agenerate([messages])
            response_text = completion.generations[0][0].text.strip()

    except Exception as e:
        # Log the error and return a generic error message
        print(f"Error in run_agent_reasoning: {str(e)}")
        response_text = "I'm sorry, but I encountered an error while processing your request. Please try again later."

    finally:
        # Always close the database connection
        if "db" in locals():
            db.close()

    # Return updated state with the response and any tool output
    return {**state, "agent_response": response_text, "tool_output": tool_output}


def generate_response(state: WhatsAppMessageState) -> dict:
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
    _user_name = state.get("user_name", "there")

    # Start building the message
    message = agent_response  # f"Hi {user_name},\n\n{agent_response}"

    # Append tool output if available and meaningful
    if tool_output:
        if isinstance(tool_output, dict):
            # Format dict nicely (simple key: value lines)
            tool_text = "\n".join(f"{k}: {v}" for k, v in tool_output.items())
            message += f"\n\nHere is the information you requested:\n{tool_text}"
        else:
            # Otherwise just append as string
            message += f"\n\n{tool_output}"

    # # Optionally add a friendly closing line
    # message += "\n\nIf you have more questions, just reply here!"

    return {**state, "final_message": message}


def send_whatsapp_message(state: WhatsAppMessageState, config: Dict[str, Any]):
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
    final_message = state.get("final_message")
    user_phone_number = state.get("user_phone_number")
    organization_phone_number = config["configurable"].get("organization_phone_number")
    print(f"final_message: {final_message}")
    print(f"user_phone_number: {user_phone_number}")
    print(f"organization_phone_number: {organization_phone_number}")

    if not all([final_message, user_phone_number, organization_phone_number]):
        raise ValueError(
            "Missing one or more required fields in state: 'final_message', 'user_phone_number', or 'organization_phone_number'."
        )

    message = client.messages.create(
        body=final_message,
        from_=f"whatsapp:{organization_phone_number}",
        to=f"{user_phone_number}"
        if user_phone_number.startswith("whatsapp:")
        else f"whatsapp:{user_phone_number}",
    )

    return {"message_sid": message.sid, "status": message.status}


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
