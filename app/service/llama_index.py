import os
from openai import OpenAI
from dotenv import load_dotenv
from llama_index.node_parser import SimpleNodeParser
from llama_index.text_splitter import TokenTextSplitter

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class LlamaIndexService:

    def __init__(self):
        """
        Initialize the LlamaIndexService.

        Creates an OpenAI client object with the OPENAI_API_KEY environment variable.
        """
        self.model = "text-embedding-ada-002"
        self.text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=20)
        self.node_parser = SimpleNodeParser(text_splitter=self.text_splitter)

        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def get_embedding(self, text: str) -> list:
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks"""
        return self.text_splitter.split_text(text)
