# 🚀 FastAPI Document Management Backend

## Overview
This is a modular, production-ready backend built with **FastAPI** for managing users, documents, and AI-assisted semantic search. The project leverages **PostgreSQL + pgvector**, **SQLAlchemy**, **Alembic**, and integrates **LangChain** + **OpenAI (GPT-4o)** for powerful document-based LLM workflows.

## Core Features
- **User Registration & Authentication:**
   - Register, login, and secure endpoints via token-based access control.
- **Document Uploads & Management:**
   - Upload and manage documents via API.
   - Each document is embedded and stored as a vector for semantic retrieval.
- **Semantic Document Search:**
    - Vector-based document search using pgvector.
    - Users can query for documents by meaning, not just keywords, via endpoints.
- **LangChain & AI Agent Integration:**
    - The codebase is already integrated with LangChain and supports LLM-based workflows (e.g., OpenAI GPT-4o).
    - Tools for natural language queries, summarization, and contextual search.
    - Core logic in `app/agent/rag_agent.py` and `rag_helper.py`.

## Roadmap/Next Steps

- **DevContainer Support:**
   - Add `.devcontainer/` with PostgreSQL & Python setup for VS Code.
- **Pluggable AI Tooling:**
   - Extend `get_tools()` to include OCR, summarization, translation, etc.
- **User Roles & Permissions:**
   - Add roles (admin, editor, viewer) with per-document permissions.
- **Frontend Development:**
   - Build a basic React/Next.js frontend for UX.
- **Performance Optimization & Deployment:**
   - Containerize the app with Docker, add production-ready settings, and prepare for cloud deployment (e.g., Railway, Azure, AWS).


## ⚙️ Installation
### Prerequisites
Ensure you have the following installed:
- Python 3.12+
- PostgreSQL
- (Optional) `virtualenv` or `venv`

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
   OPENAI_API_KEY=your-open-ai-key
   ```
5. Run database migrations:
   ```sh
   alembic revision --autogenerate -m "migration commit message"
   alembic upgrade head
   ```

## Running the Application
To start the FastAPI server, use:
```sh
uvicorn main:app --reload
```

## 📝 Notes
- Project uses pgvector for native similarity search in PostgreSQL.
- Designed for modular LLM agent workflows using LangChain + OpenAI.
- Core logic and agent tools can be extended easily for new AI capabilities.
