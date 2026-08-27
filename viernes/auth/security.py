"""
Utilidades Criptográficas y de Seguridad para V.I.E.R.N.E.S.
Implementa PBKDF2 SHA-256 (600,000 iteraciones) y firmado seguro de tokens de sesión.
"""

import os
import hmac
import hashlib
import secrets
import json
import base64
import time
from typing import Tuple, Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
SECRET_KEY_FILE = os.path.join(DATA_DIR, "auth_secret.key")


def _get_or_create_secret_key() -> bytes:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, "rb") as f:
            return f.read()
    else:
        new_key = secrets.token_bytes(32)
        with open(SECRET_KEY_FILE, "wb") as f:
            f.write(new_key)
        return new_key


SECRET_KEY = _get_or_create_secret_key()


def hash_password(password: str) -> str:
    """Hashea una contraseña usando PBKDF2-HMAC-SHA256 con salt aleatorio."""
    salt = secrets.token_bytes(16)
    iterations = 600000
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    # Formato: pbkdf2_sha256$iterations$salt_hex$key_hex
    return f"pbkdf2_sha256${iterations}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña en tiempo constante para mitigar timing attacks."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(expected_key, actual_key)
    except Exception:
        return False


def create_session_token(email: str, expires_in_seconds: int = 86400 * 7) -> str:
    """Crea un token de sesión firmado criptográficamente con HMAC-SHA256."""
    payload = {
        "email": email,
        "exp": int(time.time()) + expires_in_seconds,
        "nonce": secrets.token_hex(8)
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica la firma y expiración del token de sesión."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, signature = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            return None

        # Rellenar padding base64
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())

        if payload.get("exp", 0) < int(time.time()):
            return None # Expirado

        return payload
    except Exception:
        return None
