from fastapi import FastAPI
from app.routers import documents, user, whatsapp
import uvicorn
from app.service.ngrok.service import start_ngrok_tunnel
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")


app = FastAPI()


@app.get("/")
def read_root():
    """
    Root endpoint that provides basic API information.
    """
    return {"name": "Document, Whatsapp, Rag API", "version": "1.0", "status": "active"}


app.include_router(user.router)
# app.include_router(file.router)
app.include_router(documents.router)
app.include_router(whatsapp.router)

start_ngrok_tunnel()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
