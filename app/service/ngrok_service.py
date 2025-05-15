import os
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

NGROK_TUNNEL_URL = os.getenv("NGROK_TUNNEL_URL")


def start_ngrok_tunnel():
    ngrok.set_auth_token(os.getenv("NGROK_AUTH_TOKEN"))
    public_url = ngrok.connect(addr=8000, proto="http", domain=NGROK_TUNNEL_URL)
    print("🔗 ngrok public URL:", public_url)
