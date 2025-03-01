import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class LlamaIndexService:

    def __init__(self):
        """
        Initialize the LlamaIndexService.

        Creates an OpenAI client object with the OPENAI_API_KEY environment variable.
        """
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def get_embedding(self, text: str) -> list:
        response = self.client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
