import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents.agent import AgentExecutor
from twilio.rest import Client
from app.service.woo.service import WooService
from app.agent.tools.woo_tools import (
    WooCommerceOrderStatusTool,
    WooCommerceListProductsTool,
)
from app.service.woo.client import WooCommerceAPIClient
from typing import Dict
from app.helpers.whatsapp_helper import (
    send_whatsapp_message,
    receive_message,
    parse_intent,
    retrieve_conversation_context,
    run_agent_reasoning,
    route_tool,
    generate_response,
)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from typing import Any, List
from langgraph.prebuilt import tools_condition, ToolNode
from app.agent.models import MessageState

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
WOO_COMMERCE_BASE_URL = os.getenv("WOO_COMMERCE_BASE_URL")


class WhatsAppAgent:
    def __init__(self, account_sid, auth_token, model=None):
        self.woo_client = WooCommerceAPIClient(
            base_url=WOO_COMMERCE_BASE_URL,
            consumer_key=account_sid,
            consumer_secret=auth_token,
        )
        self.model = model or ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        self.config = {
            "configurable": {
                "model": self.model,
            }
        }
        self.graph_builder = self._build_agent()

    def get_woo_tools_for_shop(self, shop: dict):
        client = WooCommerceAPIClient(
            base_url=shop["woo_url"],
            consumer_key=shop["consumer_key"],
            consumer_secret=shop["consumer_secret"],
        )
        service = WooService(client)

        return [
            WooCommerceOrderStatusTool(service),
            WooCommerceListProductsTool(service),
        ]

    def _build_agent(self):
        """
        Build and return the workflow for the RAG agent.
        """
        workflow = StateGraph(MessageState)

        workflow.add_node("receive_message", receive_message)
        workflow.add_node("parse_intent", parse_intent)
        workflow.add_node("retrieve_context", retrieve_conversation_context)
        workflow.add_node("agent_reasoning", run_agent_reasoning)
        workflow.add_node("route_tool", route_tool)
        workflow.add_node("generate_response", generate_response)
        workflow.add_node("send_message", send_whatsapp_message)

        workflow.set_entry_point("receive_message")
        workflow.add_edge("receive_message", "parse_intent")
        workflow.add_edge("parse_intent", "retrieve_context")
        workflow.add_edge("retrieve_context", "agent_reasoning")
        workflow.add_edge("agent_reasoning", "route_tool")
        workflow.add_edge("route_tool", "generate_response")
        workflow.add_edge("generate_response", "send_message")
        workflow.add_edge("send_message", END)

        return workflow

    async def run(self, user_input: str, user_phone: str) -> Dict[str, Any]:
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

            graph = self.graph_builder.compile(checkpointer=checkpointer)

            res = await graph.ainvoke(
                {"user_input": user_input, "user_phone": user_phone}, config=self.config
            )
            return res


# Example usage
# if __name__ == "__main__":
#     account_sid = os.getenv("TWILIO_ACCOUNT_SID")
#     auth_token = os.getenv("TWILIO_AUTH_TOKEN")
#     whatsapp_agent = WhatsAppAgent(account_sid, auth_token)
#     # Handle a message (example placeholders used here)
#     user_id = "user123"
#     message = "Check my order status"
#     shop_info = {
#         "woo_url": "https://yourstore.com",
#         "consumer_key": "ck_your_key",
#         "consumer_secret": "cs_your_secret",
#     }
#     response = whatsapp_agent.handle_message(user_id, message, shop_info)
#     print(response)
