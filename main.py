from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    documents,
    user,
    whatsapp,
    whatsapp_auth,
    whatsapp_webhooks,
    whatsapp_phone_numbers,
    organization,
    services,
    service_credentials,
    woo_monitor,
    flow,
    flow_builder,
    admin,
)
from app.auth.router import router as auth_router
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
ENVIRONMENT = os.getenv("ENVIRONMENT")
APP_BASE_URL = os.getenv(
    "RAILWAY_STATIC_URL", "http://localhost:8000"
)  # Fallback to localhost in development

app = FastAPI()

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Vue dev server
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://vue-3-production-f39f.up.railway.app",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """
    Root endpoint that provides basic API information.
    """
    return {"name": "Document, Whatsapp, Rag API", "version": "1.0", "status": "active"}


app.include_router(auth_router)  # Authentication router should be first
app.include_router(organization.router)
app.include_router(user.router)
app.include_router(service_credentials.router)
app.include_router(services.router)
app.include_router(documents.router)
app.include_router(whatsapp.router)
app.include_router(whatsapp_auth.router)  # WhatsApp Tech Provider auth
app.include_router(whatsapp_phone_numbers.router)  # WhatsApp phone number management
app.include_router(whatsapp_webhooks.router)  # WhatsApp webhooks
app.include_router(woo_monitor.router)
app.include_router(flow.router)
app.include_router(flow_builder.router)  # Flow builder configuration endpoints
app.include_router(admin.router)  # Admin panel for super admins

if ENVIRONMENT == "development":
    from app.service.ngrok.service import start_ngrok_tunnel

    start_ngrok_tunnel()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
