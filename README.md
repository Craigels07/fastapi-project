# FastAPI Project

## Overview
This project is a modular, production-ready FastAPI-based backend designed for document management and user operations. It supports user registration, file/document uploads, and semantic search powered by vector embeddings. Built on PostgreSQL (with pgvector), SQLAlchemy, and Alembic, the system is optimized for LLM integration, particularly with LangChain and OpenAI models like GPT-4o.

## Features
- **User Registration & Authentication:** Secure endpoints for user sign-up, login, and token-based access control.
- **Document Uploads & Management:** Upload documents via API; automatically embed and index them for retrieval.
- **Semantic Document Search:** All documents transformed into vector embeddings upon upload, allowing for efficient semantic similarity search directly in the database. Users can query for documents by meaning, not just keywords, via endpoints.
- **LangChain & AI Agent Integration:** The codebase is already integrated with LangChain and supports LLM-based workflows (e.g., OpenAI GPT-4o). The agent can process natural language queries, use tools (such as semantic document search), and summarize conversations, as implemented in app/agent/rag_agent.py and app/agent/rag_helper.py.

## Roadmap/Next Steps

- **DevContainer Support:** Add .devcontainer/ directory with Python, PostgreSQL, and VS Code config for one-click VS Code development environments.
- **Pluggable AI Tooling:** Extend the get_tools() function to support summarization, translation, OCR, and other AI tools.
- **User Roles & Permissions:** Extend authentication to support user roles (admin, editor, viewer) and granular document access control.
- **Frontend Development:** Build a simple React or Next.js frontend for user registration, document upload, search, and chat-based interactions with the agent.
- **Performance Optimization & Deployment:** Containerize the app with Docker, add production-ready settings, and prepare for cloud deployment (e.g., Railway, Azure, AWS).


## Installation
### Prerequisites
Ensure you have the following installed:
- Python 3.12+
- PostgreSQL
- Virtual environment tool (optional but recommended)

### Setup
1. Clone the repository:
   ```sh
   git clone <repository-url>
   cd fastapi_project
   ```
2. Create and activate a virtual environment:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `.venv\Scripts\activate`
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Set up environment variables (e.g., `.env` file for database connection):
   ```
   DATABASE_URL=postgresql://user:password@localhost/dbname
   ```
5. Run database migrations:
   ```sh
   alembic upgrade head
   ```

## Running the Application
To start the FastAPI server, use:
```sh
uvicorn main:app --reload
```

## Database Migrations
To apply database migrations:
```sh
alembic revision --autogenerate -m "migration commit message"
alembic upgrade head
```
