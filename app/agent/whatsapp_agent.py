import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.service.woo.client import WooCommerceAPIClient
from typing import Dict
from app.helpers.whatsapp_helper import (
    send_whatsapp_message,
    receive_message,
    parse_intent,
    retrieve_conversation_context,
    run_agent_reasoning,
    generate_response,
    get_tools,
)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from typing import Any
from app.agent.models import WhatsAppMessageState

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
WOO_COMMERCE_BASE_URL = os.getenv("WOO_COMMERCE_BASE_URL")


class WhatsAppAgent:
    def __init__(
        self,
        account_sid=None,
        auth_token=None,
        model=None,
        organization_id=None,
        to_number=None,
    ):
        if account_sid and auth_token:
            self.woo_client = WooCommerceAPIClient(
                base_url=WOO_COMMERCE_BASE_URL,
                consumer_key=account_sid,
                consumer_secret=auth_token,
            )
        self.organization_id = organization_id
        self.model = model or ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        self.config = {
            "configurable": {
                "model": self.model,
                "tools": get_tools(),
                "woo_client": self.woo_client,
                "organization_id": self.organization_id,
                "organization_phone_number": to_number,
            }
        }
        self.workflow = self._build_agent()

    def _build_agent(self):
        """
        Build and return the workflow for the RAG agent.
        """
        workflow = StateGraph(WhatsAppMessageState)

        workflow.add_node("receive_message", receive_message)
        workflow.add_node("parse_intent", parse_intent)
        workflow.add_node("retrieve_context", retrieve_conversation_context)
        workflow.add_node("agent_reasoning", run_agent_reasoning)
        workflow.add_node("generate_response", generate_response)
        workflow.add_node("send_message", send_whatsapp_message)

        workflow.set_entry_point("receive_message")
        workflow.add_edge("receive_message", "parse_intent")
        workflow.add_edge("parse_intent", "retrieve_context")
        workflow.add_edge("retrieve_context", "agent_reasoning")
        workflow.add_edge("agent_reasoning", "generate_response")
        workflow.add_edge("generate_response", "send_message")
        workflow.add_edge("send_message", END)

        return workflow

    async def run(
        self, user_input: str, whatsapp_message_id: str, user_phone_number: str
    ) -> Dict[str, Any]:
        """
        Run the RAG agent asynchronously on a list of messages.
        Uses an async Postgres checkpointer and connection pool.
        """
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }
        async with AsyncConnectionPool(
            conninfo=DATABASE_URL,
            max_size=10,
            kwargs=connection_kwargs,
        ) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()

            # Compile the graph with the checkpointer
            compiled_graph = self.workflow.compile(checkpointer=checkpointer)

            # Create initial state with user input and phone number
            initial_state = {
                "received_message": user_input,
                "whatsapp_message_id": whatsapp_message_id,
                "organization_id": self.organization_id,
                "user_phone_number": user_phone_number,
            }

            config = self.config.copy()
            config["configurable"] = self.config["configurable"].copy()
            config["configurable"]["thread_id"] = f"whatsapp_{user_phone_number}"

            # Invoke the graph with the initial state
            result = await compiled_graph.ainvoke(initial_state, config=config)

            # Return the final result
            return result
