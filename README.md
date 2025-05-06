# FastAPI Project

## Overview
This is a FastAPI-based project designed to handle file uploads and user management. It utilizes PostgreSQL as the database, SQLAlchemy for ORM, and Alembic for database migrations.

## Features
- User Registration
- Document uploads and management
- Document search using semantic similarity
- Database-backed storage with PostgreSQL
- Automatic schema migrations with Alembic

## Next Steps
- Connect LangChain for query processing
- DevContainer for testing
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
uvicorn main:app --reload
```

## Database Migrations
To apply database migrations:
```sh
python -m alembic revision --autogenerate -m "update document model"
alembic revision --autogenerate -m "create_documents_table"
python -m alembic upgrade head
alembic upgrade head
```
