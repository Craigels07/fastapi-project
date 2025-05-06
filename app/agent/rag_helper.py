
from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from app.helpers.collection_helpers import get_or_create_collection
from dotenv import load_dotenv
import os
from app.database import SessionLocal
from typing import Dict, Any, List
from app.schemas.document import SearchResponse
# Models:
from app.agent.models import MessageState


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


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
    
    return {
        "messages": response,
        "summary": summary
    }

def summarize_conversation(state: MessageState, config: Dict[str, Any]):
    """
    Summarize the conversation by creating a new summary based on the existing summary and new messages.
    If no summary exists, create one from the messages.
    """
    model = config["configurable"]["model"]

    # First, we get any existing summary
    summary = state.get("summary", "")

    # Create our summarization prompt
    if summary:

        # A summary already exists
        summary_message = (
            f"This is summary of the conversation to date: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )

    else:
        summary_message = "Create a summary of the conversation above:"

    # Add prompt to our history
    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = model.invoke(messages)

    # Delete all but the 2 most recent messages
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {"summary": response.content, "messages": delete_messages, "model": model}

def should_continue(state: MessageState, config: Dict[str, Any]):
    """Return the next node to execute."""

    messages = state["messages"]

    # If there are more than six messages, then we summarize the conversation
    if len(messages) > 6:
        return "summarize_conversation"

    # Determine whether to end or summarize the conversation
    return END

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

        embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model="text-embedding-3-small")

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
                similarity=result.metadata.get("similarity", 1.0) 
            )
        )

    return responses

def get_tools():
    """Get the tools available to the agent."""
    return [search_documents]

def model_with_tools():
    """
    Return a model with tools bound.
    """
    tools = get_tools()
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    llm_with_tools = model.bind_tools(tools)
    return llm_with_tools