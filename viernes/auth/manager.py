"""
Gestor de Usuarios y Autenticación para V.I.E.R.N.E.S.
Manejo seguro de usuarios en SQLite con inicialización de cuenta principal.
"""

import os
import sqlite3
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from viernes.auth.security import hash_password, verify_password, create_session_token, verify_session_token

logger = logging.getLogger("viernes.auth")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
USERS_DB = os.path.join(DATA_DIR, "users.db")

# Credenciales por defecto para inicialización
DEFAULT_ADMIN_EMAIL = "brunourrea502@gmail.com"
DEFAULT_ADMIN_PASSWORD_RAW = "g-wv.+%]r+9z5BdyKkpECu,~tWLa]-3*Wok"


class AuthManager:
    def __init__(self, db_path: str = USERS_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'admin',
                    created_at TEXT NOT NULL,
                    last_login TEXT
                )
            """)
            conn.commit()

            # Sembrar cuenta de administrador inicial si no existe
            cursor = conn.execute("SELECT id FROM users WHERE email = ?", (DEFAULT_ADMIN_EMAIL,))
            if not cursor.fetchone():
                hashed = hash_password(DEFAULT_ADMIN_PASSWORD_RAW)
                now = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO users (email, password_hash, role, created_at)
                    VALUES (?, ?, 'admin', ?)
                """, (DEFAULT_ADMIN_EMAIL, hashed, now))
                conn.commit()
                logger.info(f"Usuario administrador inicial sembrado: {DEFAULT_ADMIN_EMAIL}")

    def authenticate(self, email: str, password: str) -> Optional[str]:
        """Autentica un usuario y retorna un token de sesión si es válido."""
        clean_email = email.strip().lower()
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT password_hash FROM users WHERE LOWER(email) = ?", (clean_email,))
            row = cursor.fetchone()
            if row and verify_password(password, row["password_hash"]):
                now = datetime.now().isoformat()
                conn.execute("UPDATE users SET last_login = ? WHERE LOWER(email) = ?", (now, clean_email))
                conn.commit()
                return create_session_token(clean_email)
        return None

    def reset_password(self, email: str, new_password: str) -> bool:
        """Restablece la contraseña de un usuario (Función exclusiva para CLI)."""
        clean_email = email.strip().lower()
        new_hash = hash_password(new_password)
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id FROM users WHERE LOWER(email) = ?", (clean_email,))
            if cursor.fetchone():
                conn.execute("UPDATE users SET password_hash = ? WHERE LOWER(email) = ?", (new_hash, clean_email))
                conn.commit()
                logger.info(f"Contraseña actualizada para {clean_email} vía CLI.")
                return True
            else:
                # Si el usuario no existía, crearlo
                now = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO users (email, password_hash, role, created_at)
                    VALUES (?, ?, 'admin', ?)
                """, (clean_email, new_hash, now))
                conn.commit()
                logger.info(f"Usuario {clean_email} creado con nueva contraseña vía CLI.")
                return True

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Verifica si un token de sesión es válido."""
        return verify_session_token(token)


auth_mgr = AuthManager()
