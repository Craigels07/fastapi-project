import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Get encryption key from environment variables or generate one
# In production, this key should be set in environment variables and never committed to version control
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(
        f"WARNING: ENCRYPTION_KEY not found in environment. Generated temporary key: {ENCRYPTION_KEY}"
    )
    print(
        "Add this key to your .env file as ENCRYPTION_KEY for persistent encryption/decryption"
    )

# Initialize Fernet cipher with the key
cipher_suite = Fernet(
    ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
)


def encrypt_data(data: str) -> str:
    """
    Encrypt sensitive data like API keys

    Args:
        data: The string data to encrypt

    Returns:
        Encrypted data as a string
    """
    if not data:
        return ""

    encrypted_data = cipher_suite.encrypt(data.encode())
    return encrypted_data.decode()


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt sensitive data like API keys

    Args:
        encrypted_data: The encrypted data string

    Returns:
        Decrypted data as a string
    """
    if not encrypted_data:
        return ""

    decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
    return decrypted_data.decode()
