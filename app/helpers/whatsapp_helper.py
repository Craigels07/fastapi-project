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
                service_credentials = list(db.query(ServiceCredential).filter_by(organization_id=organization_id))
                # Convert SQLAlchemy models to dictionaries for ServiceRegistry
                organization_services = []
                for cred in service_credentials:
                    # Convert enum to string if it's an enum
                    service_type = cred.service_type.value if hasattr(cred.service_type, 'value') else str(cred.service_type)
                    
                    # Decrypt the credentials
                    try:
                        from app.utils.encryption import decrypt_data
                        import json
                        
                        # Decrypt the credentials and parse as JSON
                        decrypted_json = decrypt_data(cred.credentials)
                        credentials_dict = json.loads(decrypted_json)
                    except Exception as e:
                        print(f"Error decrypting credentials: {e}")
                        credentials_dict = {}
                    
                    # Create dict with required service_type key and other useful attributes
                    service_dict = {
                        "service_type": service_type,
                        "credentials": credentials_dict,  # Use decrypted credentials dictionary
                        "organization_id": str(cred.organization_id),
                        "is_active": cred.is_active.lower() == 'true' if isinstance(cred.is_active, str) else bool(cred.is_active),
                        "id": str(cred.id)
                    }
                    organization_services.append(service_dict)
                print(f"Available services for organization {organization.id}: {organization_services}")
            except Exception as e:
                # Handle case where table doesn't exist or other DB errors
                print(f"Error fetching service credentials: {e}")
                organization_services = []

        # Print debug information about message details
        print(f"Message purpose: {messagePurpose}")
        print(f"Message details: {messageDetails}")
        
        # Normalize message details keys to match what services expect
        normalized_details = {}
        
        # Include user phone number from state for security verification
        if "user_phone_number" in state:
            normalized_details["user_phone_number"] = state.get("user_phone_number")
        
        # Ensure messageDetails is a dictionary
        if not isinstance(messageDetails, dict):
            print(f"Warning: messageDetails is not a dictionary. Type: {type(messageDetails)}, Value: {messageDetails}")
            # Convert to dictionary if possible
            if isinstance(messageDetails, str):
                # Check for patterns like "Order ID 41642"
                import re
                
                # For order queries
                order_id_match = re.search(r'order\s*id\s*(\d+)', messageDetails, re.IGNORECASE)
                if order_id_match and messagePurpose.lower().replace(" ", "_") == "order_query":
                    order_id = order_id_match.group(1)
                    normalized_details["order_id"] = order_id
                    print(f"Extracted order ID: {order_id} from string message details")
                else:
                    # If it's just a string, treat it as general query
                    normalized_details["query"] = messageDetails
            else:
                # Default to empty dictionary if we can't process it
                if "user_phone_number" not in normalized_details and "user_phone_number" in state:
                    normalized_details["user_phone_number"] = state.get("user_phone_number")
        else:
            # Map specific keys to match service expectations
            try:
                if "order ID" in messageDetails:
                    normalized_details["order_id"] = messageDetails["order ID"]
                
                if "product name" in messageDetails:
                    normalized_details["product_name"] = messageDetails["product name"]
                    
                if "product description" in messageDetails:
                    normalized_details["product_description"] = messageDetails["product description"]
                    
                # Add any other keys directly
                for key, value in messageDetails.items():
                    if key not in ["order ID", "product name", "product description"]:
                        normalized_details[key] = value
            except Exception as e:
                print(f"Error normalizing message details: {e}")
                # Provide a simple fallback with the original message details
                normalized_details = {"original": str(messageDetails)}
                if "user_phone_number" in state:
                    normalized_details["user_phone_number"] = state.get("user_phone_number")
        
        # Always ensure we have a normalized purpose
        normalized_purpose = messagePurpose.lower().replace(" ", "_") if isinstance(messagePurpose, str) else "unknown"
                
        print(f"Normalized message purpose: {normalized_purpose}")
        print(f"Normalized message details: {normalized_details}")
        
        # For each service, initialize the client explicitly
        for service_config in organization_services:
            if service_config["service_type"] == "woocommerce":
                from app.service.woo.client import WooCommerceAPIClient
                # Get credentials
                creds = service_config.get("credentials", {})
                woo_url = creds.get("woo_url")
                consumer_key = creds.get("consumer_key")
                consumer_secret = creds.get("consumer_secret")
                
                if woo_url and consumer_key and consumer_secret:
                    # Initialize the client
                    try:
                        client = WooCommerceAPIClient(woo_url, consumer_key, consumer_secret)
                        # Add the client to the service config
                        service_config["client"] = client
                        print(f"WooCommerce client initialized with URL: {woo_url}")
                    except Exception as e:
                        print(f"Error initializing WooCommerce client: {e}")
        
        # Find a service that can handle this message purpose
        service = ServiceRegistry.find_capable_service(
            organization_services=organization_services,
            message_purpose=normalized_purpose,
            message_details=normalized_details,
        )
        print(f"service were found {service}")
        # If we found a capable service, let it process the request
        if service:
            # Process the request using the service with normalized details
            result = service.process_request(normalized_purpose, normalized_details)
            response_text = result.get("response_text", "")
            tool_output = result.get("tool_output")
            print(f"Service processed request and returned: {result}")
        # Fall back to generic responses if no service can handle it
        elif normalized_purpose == "order_query":
            response_text = "It looks like you're asking about an order, but I don't have access to your order information right now."
        elif normalized_purpose == "get_product_info":
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

    # Append tool output if available and meaningful, but be selective to avoid exceeding WhatsApp's 1600 char limit
    if tool_output:
        if isinstance(tool_output, dict):
            # For order queries, create a clean, concise order summary
            if 'id' in tool_output and 'status' in tool_output:  # This looks like an order
                # Format order summary with minimal repetition
                order_id = tool_output.get('id', 'Unknown')
                status = tool_output.get('status', 'Unknown')
                
                # Format date in a more readable way if available
                date_str = tool_output.get('date_created', '')
                date_formatted = date_str.split('T')[0] if 'T' in date_str else date_str
                
                # Format currency properly
                currency_symbol = tool_output.get('currency_symbol', '')
                total = tool_output.get('total', '0.00')
                formatted_total = f"{currency_symbol}{total}" if currency_symbol else total
                
                # Start with a clean, concise header
                order_summary = [f"Order #{order_id}"]
                
                # Add core order information
                if status:
                    order_summary.append(f"Status: {status}")
                if date_formatted:
                    order_summary.append(f"Date: {date_formatted}")
                if formatted_total:
                    order_summary.append(f"Total: {formatted_total}")
                
                # Add payment method if available
                payment_method = tool_output.get('payment_method_title', '')
                if payment_method:
                    order_summary.append(f"Payment: {payment_method}")
                    
                # Format items section
                items_text = ""
                if 'line_items' in tool_output and isinstance(tool_output['line_items'], list) and tool_output['line_items']:
                    items_text = "\n\nItems:"  # Double newline for separation
                    for item in tool_output['line_items'][:5]:  # Show up to 5 items
                        name = item.get('name', 'Unknown product')
                        qty = item.get('quantity', 1)
                        price = item.get('total', '0.00')
                        items_text += f"\n• {name} x{qty} ({currency_symbol}{price})"
                    
                    if len(tool_output['line_items']) > 5:
                        items_text += f"\n• ... and {len(tool_output['line_items']) - 5} more item(s)"
                
                # Combine everything into a clean message
                order_text = "\n".join(order_summary)
                message += f"\n\n{order_text}{items_text}"
            else:
                # For other dictionaries, limit to 10 key-value pairs and 800 chars total
                tool_items = list(tool_output.items())[:10]
                tool_text = "\n".join(f"{k}: {v}" for k, v in tool_items)
                if len(tool_text) > 800:
                    tool_text = tool_text[:797] + "..."
                message += f"\n\nHere is the information you requested:\n{tool_text}"
        else:
            # If it's a string or other type, truncate if needed
            tool_output_str = str(tool_output)
            if len(tool_output_str) > 800:
                tool_output_str = tool_output_str[:797] + "..."
            message += f"\n\n{tool_output_str}"
    
    # Ensure the final message is under 1600 characters (WhatsApp limit)
    if len(message) > 1550:  # Leave some buffer
        message = message[:1547] + "..."

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
