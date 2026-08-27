"""
Cliente de Google Gmail API para V.I.E.R.N.E.S.
Consulta correos no leídos, extrae contenido y aplica filtro inteligente.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from viernes.mail.ai_triage import EmailTriageEngine

logger = logging.getLogger("viernes.mail.gmail")


class GmailClient:
    def __init__(self, token_path: str = "config/gmail_token.json", credentials_path: str = "config/gmail_credentials.json"):
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.service = None
        self._init_service()

    def _init_service(self):
        """Inicializa el cliente de Gmail si existen las credenciales OAuth2."""
        if not os.path.exists(self.token_path) and not os.path.exists(self.credentials_path):
            logger.debug("Credenciales de Gmail no configuradas todavía. Modo Standby.")
            return

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, ["https://www.googleapis.com/auth/gmail.readonly"])
                self.service = build("gmail", "v1", credentials=creds)
                logger.info("Cliente de Gmail conectado exitosamente vía OAuth2.")
        except Exception as e:
            logger.error(f"Error inicializando Gmail API: {e}")

    async def get_unread_emails(self, max_results: int = 10, only_important: bool = True) -> List[Dict[str, Any]]:
        """Obtiene y clasifica los correos no leídos de la bandeja de entrada."""
        if not self.service:
            logger.debug("Servicio de Gmail no inicializado; retornando datos de demostración si aplica.")
            return []

        try:
            results = self.service.users().messages().list(
                userId="me", q="is:unread label:INBOX", maxResults=max_results
            ).execute()
            messages = results.get("messages", [])

            emails = []
            for msg in messages:
                detail = self.service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
                headers = {h["name"].lower(): h["value"] for h in detail.get("payload", {}).get("headers", [])}
                
                email_item = {
                    "id": msg["id"],
                    "source": "Gmail",
                    "sender": headers.get("from", "Desconocido"),
                    "subject": headers.get("subject", "(Sin Asunto)"),
                    "date": headers.get("date", ""),
                    "snippet": detail.get("snippet", ""),
                }
                emails.append(email_item)

            if only_important:
                return EmailTriageEngine.filter_important_emails(emails)
            return emails
        except Exception as e:
            logger.error(f"Error consultando correos en Gmail: {e}")
            return []


gmail_client = GmailClient()
