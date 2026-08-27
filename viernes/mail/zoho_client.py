"""
Cliente de Zoho Mail (IMAP / SSL) para V.I.E.R.N.E.S.
Permite consultar la bandeja de entrada de Zoho y aplicar filtrado inteligente con IA.
"""

import os
import imaplib
import email
from email.header import decode_header
import logging
from typing import List, Dict, Any
from viernes.mail.ai_triage import EmailTriageEngine

logger = logging.getLogger("viernes.mail.zoho")


class ZohoMailClient:
    def __init__(self, username: str = None, password: str = None, server: str = "imappro.zoho.com", port: int = 993):
        self.username = username or os.getenv("ZOHO_EMAIL", "")
        self.password = password or os.getenv("ZOHO_PASSWORD", "")
        self.server = server or os.getenv("ZOHO_IMAP_SERVER", "imappro.zoho.com")
        self.port = port

    def _decode_str(self, header_value: str) -> str:
        if not header_value:
            return ""
        decoded_list = decode_header(header_value)
        text_parts = []
        for text, encoding in decoded_list:
            if isinstance(text, bytes):
                try:
                    text_parts.append(text.decode(encoding or "utf-8", errors="ignore"))
                except Exception:
                    text_parts.append(text.decode("latin-1", errors="ignore"))
            else:
                text_parts.append(str(text))
        return "".join(text_parts)

    def get_unread_emails(self, max_results: int = 10, only_important: bool = True) -> List[Dict[str, Any]]:
        """Consulta correos no leídos en Zoho Mail de forma sincrónica o en thread."""
        if not self.username or not self.password or self.password.startswith("tu_"):
            logger.debug("Credenciales de Zoho Mail no configuradas. Standby.")
            return []

        emails = []
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.username, self.password)
            mail.select("INBOX")

            # Buscar correos no leídos
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages[0]:
                mail.close()
                mail.logout()
                return []

            msg_ids = messages[0].split()
            # Tomar los últimos max_results
            recent_ids = msg_ids[-max_results:]

            for m_id in reversed(recent_ids):
                res, msg_data = mail.fetch(m_id, "(RFC822.HEADER)")
                if res != "OK":
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = self._decode_str(msg.get("Subject", "(Sin Asunto)"))
                        sender = self._decode_str(msg.get("From", "Desconocido"))
                        date = msg.get("Date", "")

                        emails.append({
                            "id": m_id.decode() if isinstance(m_id, bytes) else str(m_id),
                            "source": "Zoho Mail",
                            "sender": sender,
                            "subject": subject,
                            "date": date,
                            "snippet": f"De: {sender} - Asunto: {subject}",
                        })

            mail.close()
            mail.logout()

            if only_important:
                return EmailTriageEngine.filter_important_emails(emails)
            return emails
        except Exception as e:
            logger.error(f"Error consultando Zoho Mail vía IMAP: {e}")
            return []


zoho_client = ZohoMailClient()
