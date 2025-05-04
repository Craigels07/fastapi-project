import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from typing import Any, Dict, List, Optional
from IPython.display import Image, display
from langgraph.prebuilt import tools_condition, ToolNode
# Models:
from app.agent.models import MessagState

# Helpers:
from app.agent.rag_helper import call_model, summarize_conversation, should_continue, get_tools


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

class RagAgent:
    """
    Retrieval-Augmented Generation (RAG) Agent for conversational workflows.
    """

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        
        self.model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        self.llm_with_tools = self.model.bind_tools(get_tools())
        self.config = {"configurable": {"thread_id": thread_id}, "model": self.llm_with_tools,}
        self.workflow = self._build_agent()

    @staticmethod
    def _build_agent():
        """
        Build and return the workflow for the RAG agent.
        """
        workflow = StateGraph(MessagState)
        workflow.add_node("conversation", call_model)
        workflow.add_node("tools", ToolNode(get_tools()))
        workflow.add_node("summarize_conversation", summarize_conversation)

        workflow.add_edge(START, "conversation")
        workflow.add_conditional_edges("conversation", tools_condition)
        workflow.add_edge("tools", "conversation")

        workflow.add_conditional_edges("conversation", should_continue)
        workflow.add_edge("summarize_conversation", END)
        return workflow

    async def run(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            max_size=20,
            kwargs=connection_kwargs,
        ) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            graph = self.workflow.compile(checkpointer=checkpointer)

            res = await graph.ainvoke({"messages": messages, "model": self.llm_with_tools}, config=self.config)            # checkpoint = await checkpointer.get(self.config)
            return res

    async def get_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest checkpoint for the current thread.
        """
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }
        async with AsyncConnectionPool(
            conninfo=DATABASE_URL,
            max_size=20,
            kwargs=connection_kwargs,
        ) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            return await checkpointer.aget(self.config)
    
    async def display_graph(self):
        """Display workflow graph using an async checkpointer."""
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }
        try:
            async with AsyncConnectionPool(
                conninfo=DATABASE_URL,
                max_size=20,
                kwargs=connection_kwargs,
            ) as pool:
                checkpointer = AsyncPostgresSaver(pool)
                await checkpointer.setup()
                graph = self.workflow.compile(checkpointer=checkpointer)
                img = Image(graph.get_graph().draw_mermaid_png())
                display(img)
        except Exception as e:
            print(f"Could not display workflow graph: {e}")
        
    
