"""
the ONLY place passwords are hashed and card numbers are encrypted
Everyone should call these helpers instead of touching bcrypt/Fernet directly
"""
import os
import hashlib
import secrets

import bcrypt
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

_key = os.getenv("CARD_ENCRYPTION_KEY")
if not _key:
    raise RuntimeError(
        "CARD_ENCRYPTION_KEY is missing from .env. Generate one with:\n"
        '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    )
_fernet = Fernet(_key.encode())


# Passwords (one-way bcrypt hash) 
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# Card numbers (reversible Fernet encryption) 
def encrypt_card(card_number: str) -> str:
    return _fernet.encrypt(card_number.encode()).decode()


def decrypt_card(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


# Email verification / password reset tokens
def generate_token() -> str:
    """Random URL-safe token. Email this one; store only its hash."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()