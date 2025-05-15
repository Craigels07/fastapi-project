from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.agents.agent import AgentExecutor
from twilio.rest import Client

from typing import Dict


class WhatsAppAgent:
    def __init__(self, account_sid, auth_token):
        self.agents: Dict[str, AgentExecutor] = {}
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.client = Client(self.account_sid, self.auth_token)

    def send_whatsapp_message(self, body, from_number, to_number):
        _message = self.client.messages.create(
            body=body,
            from_=f"whatsapp:+{from_number}",
            to=f"whatsapp:+{to_number}",
        )

    def get_agent(self, user_id: str) -> AgentExecutor:
        """
        Get or create a LangChain agent instance for a given WhatsApp user.
        """
        if user_id not in self.agents:
            llm = ChatOpenAI(temperature=0.7)
            memory = ConversationBufferMemory(
                memory_key="chat_history", return_messages=True
            )
            agent = initialize_agent(
                tools=[],  # Add tools here if needed
                llm=llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                memory=memory,
                verbose=True,
            )
            self.agents[user_id] = agent
        return self.agents[user_id]

    async def handle_message(self, user_id: str, message: str) -> str:
        """
        Process an incoming message and return the agent's response.
        """
        agent = self.get_agent(user_id)
        try:
            response = await agent.ainvoke({"input": message})
            return str(response.get("output", response))
        except Exception as e:
            return f"Sorry, an error occurred: {str(e)}"
