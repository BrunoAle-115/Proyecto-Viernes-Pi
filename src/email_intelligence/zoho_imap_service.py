"""
V.I.E.R.N.E.S Zoho Mail (IMAP/SSL) Service
Handles secure IMAP connection, mailbox traversal, raw RFC822 parsing, IDLE push loops, and flags.
"""

import asyncio
from datetime import datetime, timezone
import email
from email.header import decode_header
import imaplib
import logging
import ssl
from typing import AsyncGenerator, Callable, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from src.config import settings
from src.email_intelligence.models import EmailSource, UnifiedEmail

logger = logging.getLogger("VIERNES.ZohoIMAPService")


def _decode_mime_words(header_value: Optional[str]) -> str:
    """Safely decodes RFC 2047 encoded header strings into unicode."""
    if not header_value:
        return ""
    decoded_fragments = decode_header(header_value)
    result = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            if encoding:
                try:
                    result.append(fragment.decode(encoding, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    result.append(fragment.decode("utf-8", errors="replace"))
            else:
                result.append(fragment.decode("utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result).strip()


class ZohoIMAPService:
    """
    Asynchronous IMAP client configured for Zoho Mail with SSL and RFC 822 decoding.
    """

    def __init__(
        self,
        server: str = settings.ZOHO_IMAP_SERVER,
        port: int = settings.ZOHO_IMAP_PORT,
        username: Optional[str] = settings.ZOHO_EMAIL_USER,
        password: Optional[str] = settings.ZOHO_EMAIL_PASSWORD,
        use_ssl: bool = settings.ZOHO_IMAP_USE_SSL,
    ):
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def connect_sync(self) -> imaplib.IMAP4_SSL:
        """Establishes SSL connection and authenticates with Zoho Mail."""
        if not self.username or not self.password:
            raise ValueError(
                "Zoho IMAP credentials not configured. Please set ZOHO_EMAIL_USER and ZOHO_EMAIL_PASSWORD."
            )

        ssl_context = ssl.create_default_context()
        logger.info(f"Connecting to Zoho IMAP ({self.server}:{self.port})...")
        imap = imaplib.IMAP4_SSL(self.server, self.port, ssl_context=ssl_context)
        imap.login(self.username, self.password)
        self._imap = imap
        logger.info(f"Successfully authenticated Zoho IMAP for {self.username}")
        return imap

    async def connect(self) -> imaplib.IMAP4_SSL:
        return await asyncio.to_thread(self.connect_sync)

    def _ensure_connected(self):
        try:
            if not self._imap or self._imap.state == "LOGOUT":
                self.connect_sync()
            else:
                self._imap.noop()
        except Exception:
            logger.info("Re-establishing IMAP connection...")
            self.connect_sync()

    async def fetch_unread_messages(
        self, folder: str = "INBOX", limit: int = 30
    ) -> List[UnifiedEmail]:
        """Fetches unread (UNSEEN) emails from the specified mailbox folder."""
        return await asyncio.to_thread(self._fetch_unread_sync, folder, limit)

    def _fetch_unread_sync(self, folder: str, limit: int) -> List[UnifiedEmail]:
        self._ensure_connected()
        self._imap.select(folder)
        
        status, data = self._imap.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return []

        message_ids = data[0].split()
        # Grab the newest messages first
        message_ids = message_ids[-limit:]
        parsed_emails: List[UnifiedEmail] = []

        for msg_id_bytes in message_ids:
            msg_id_str = msg_id_bytes.decode()
            status, msg_data = self._imap.fetch(msg_id_bytes, "(RFC822)")
            if status != "OK" or not msg_data:
                continue

            raw_rfc822_bytes = None
            for part in msg_data:
                if isinstance(part, tuple) and len(part) >= 2:
                    raw_rfc822_bytes = part[1]
                    break

            if raw_rfc822_bytes:
                email_obj = self.parse_rfc822_message(msg_id_str, raw_rfc822_bytes)
                parsed_emails.append(email_obj)

        return parsed_emails

    def parse_rfc822_message(self, imap_uid: str, raw_bytes: bytes) -> UnifiedEmail:
        """
        Parses raw RFC 822 email bytes into a standardized UnifiedEmail object.
        """
        msg = email.message_from_bytes(raw_bytes)
        
        # Headers extraction
        headers_map: Dict[str, str] = {}
        for k, v in msg.items():
            headers_map[k.lower()] = _decode_mime_words(v)

        subject = _decode_mime_words(msg.get("Subject", "(No Subject)"))
        from_header = _decode_mime_words(msg.get("From", ""))
        to_header = _decode_mime_words(msg.get("To", ""))
        cc_header = _decode_mime_words(msg.get("Cc", ""))
        date_header = msg.get("Date", "")
        message_id = msg.get("Message-ID", None)
        in_reply_to = msg.get("In-Reply-To", None)

        sender_name, sender_email = email.utils.parseaddr(from_header)
        if not sender_email:
            sender_email = from_header

        to_list = [addr[1] for addr in email.utils.getaddresses([to_header]) if addr[1]]
        cc_list = [addr[1] for addr in email.utils.getaddresses([cc_header]) if addr[1]]

        parsed_date = datetime.now(timezone.utc)
        if date_header:
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_header)
            except Exception:
                pass

        # Multipart body parsing
        body_text, body_html, attachments = self._extract_mime_payload(msg)

        # Fallback to HTML stripping if plain text is missing
        if not body_text.strip() and body_html.strip():
            soup = BeautifulSoup(body_html, "html.parser")
            body_text = soup.get_text(separator="\n").strip()

        snippet = (body_text[:160] + "...") if len(body_text) > 160 else body_text

        return UnifiedEmail(
            id=imap_uid,
            source=EmailSource.ZOHO_IMAP,
            thread_id=in_reply_to or message_id or imap_uid,
            message_id_header=message_id,
            in_reply_to=in_reply_to,
            sender_name=sender_name if sender_name else None,
            sender_email=sender_email.lower(),
            recipient_emails=[e.lower() for e in to_list],
            cc_emails=[e.lower() for e in cc_list],
            subject=subject,
            date=parsed_date,
            body_text=body_text,
            body_html=body_html if body_html else None,
            snippet=snippet,
            has_attachments=len(attachments) > 0,
            attachment_filenames=attachments,
            headers=headers_map,
            labels=["UNREAD"],
            is_unread=True,
        )

    def _extract_mime_payload(self, msg: email.message.Message) -> Tuple[str, str, List[str]]:
        body_text = ""
        body_html = ""
        attachment_names: List[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                filename = part.get_filename()

                if filename:
                    attachment_names.append(_decode_mime_words(filename))
                    continue

                if "attachment" in content_disposition:
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                charset = part.get_content_charset() or "utf-8"
                try:
                    text_decoded = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    text_decoded = payload.decode("utf-8", errors="replace")

                if content_type == "text/plain":
                    body_text += "\n" + text_decoded
                elif content_type == "text/html":
                    body_html += "\n" + text_decoded
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    text_decoded = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    text_decoded = payload.decode("utf-8", errors="replace")

                if msg.get_content_type() == "text/html":
                    body_html = text_decoded
                else:
                    body_text = text_decoded

        return body_text.strip(), body_html.strip(), attachment_names

    async def mark_as_read(self, imap_uid: str, folder: str = "INBOX"):
        """Flags the message as \\Seen on Zoho Mail."""
        await asyncio.to_thread(self._mark_as_read_sync, imap_uid, folder)

    def _mark_as_read_sync(self, imap_uid: str, folder: str):
        self._ensure_connected()
        self._imap.select(folder)
        self._imap.store(imap_uid.encode(), "+FLAGS", "\\Seen")

    async def start_idle_listener(
        self, folder: str = "INBOX", on_new_email_callback: Optional[Callable[[], None]] = None
    ):
        """
        Runs an IMAP IDLE push loop (or periodic fallback) to detect incoming emails in real-time.
        """
        while True:
            try:
                await asyncio.to_thread(self._ensure_connected)
                # Note: Standard Python imaplib doesn't support async IDLE out of the box without raw socket manipulation,
                # so we combine standard NOOP checks with configurable intervals or aioimaplib.
                new_emails = await self.fetch_unread_messages(folder=folder, limit=5)
                if new_emails and on_new_email_callback:
                    on_new_email_callback()
            except Exception as e:
                logger.error(f"Zoho IMAP listener encountered error: {e}")
            await asyncio.sleep(settings.ZOHO_POLL_INTERVAL_SECONDS)
