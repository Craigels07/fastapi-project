import os
from langchain_openai import ChatOpenAI
from openai import OpenAI
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class LlamaIndexService:
    def __init__(self):
        """
        Initialize the LlamaIndexService.

        Creates an OpenAI client object with the OPENAI_API_KEY environment variable.
        """
        self.model = "text-embedding-ada-002"
        self.embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def get_embedding(self, text: str) -> list:
        """Get embeddings using LangChain"""
        return self.embeddings.embed_query(text)

    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks"""
        return self.text_splitter.split_text(text)

    def ask_question(self, question: str, docs: list[str]) -> str:
        """Answer questions using retrieved documents"""
        context = "\n\n".join(docs)
        prompt = f"Based on the following context, answer this question: {question}\n\nContext: {context}"
        response = self.llm.predict(prompt)
        return response
