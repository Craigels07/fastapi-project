# FastAPI Project

## Overview
This is a FastAPI-based project designed to handle file uploads and user management. It utilizes PostgreSQL as the database, SQLAlchemy for ORM, and Alembic for database migrations.

## Features
- User Registration
- File uploads and management
- Database-backed storage with PostgreSQL
- Automatic schema migrations with Alembic

## Next Steps
- Integrate LlamaIndex for indexing & retrieval
- Connect LangChain for query processing
- Integrate LLM (OpenAI API)
- Enable streaming responses for better UX
- Build a simple frontend (React, Next.js)
- Optimize performance & deploy (Docker)

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
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
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
uvicorn app.main:app --reload
```

