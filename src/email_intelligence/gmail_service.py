"""
V.I.E.R.N.E.S Gmail API Service
Handles OAuth2 lifecycle, message fetching, MIME structure parsing, and label management.
"""

import asyncio
import base64
import email
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from src.config import settings
from src.email_intelligence.models import EmailSource, UnifiedEmail

logger = logging.getLogger("VIERNES.GmailService")


class GmailService:
    """
    Asynchronous wrapper and parser for the Google Gmail REST API (OAuth2).
    """

    def __init__(
        self,
        credentials_file: str = settings.GMAIL_CREDENTIALS_FILE,
        token_file: str = settings.GMAIL_TOKEN_FILE,
        scopes: Optional[List[str]] = None,
        user_id: str = settings.GMAIL_USER_ID,
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.scopes = scopes or settings.GMAIL_SCOPES
        self.user_id = user_id
        self._service: Optional[Resource] = None
        self._creds: Optional[Credentials] = None
        self._label_cache: Dict[str, str] = {}  # name -> id

    def is_authenticated(self) -> bool:
        return self._creds is not None and self._creds.valid

    def authenticate_sync(self) -> Credentials:
        """
        Authenticates via existing token or triggers the OAuth2 local server flow.
        """
        creds = None
        # Load existing token if available
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            except Exception as e:
                logger.warning(f"Failed to load token file {self.token_file}: {e}")

        # Refresh or prompt authorization
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired Gmail OAuth2 token...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Gmail OAuth2 credentials file not found at: {self.credentials_file}. "
                        "Please place your Google Cloud OAuth client credentials JSON in this path."
                    )
                logger.info("Initiating OAuth2 authorization flow for Gmail...")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.scopes)
                creds = flow.run_local_server(port=0)

            # Ensure parent directories exist and persist token
            os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())
            logger.info(f"Saved renewed Gmail token to {self.token_file}")

        self._creds = creds
        self._service = build("gmail", "v1", credentials=self._creds, cache_discovery=False)
        return creds

    async def authenticate(self) -> Credentials:
        return await asyncio.to_thread(self.authenticate_sync)

    def _ensure_service(self):
        if not self._service:
            self.authenticate_sync()

    async def fetch_unread_messages(
        self, query: str = "is:unread", max_results: int = 30
    ) -> List[UnifiedEmail]:
        """
        Fetches and parses unread messages from Gmail matching the search query.
        """
        return await asyncio.to_thread(self._fetch_unread_messages_sync, query, max_results)

    def _fetch_unread_messages_sync(self, query: str, max_results: int) -> List[UnifiedEmail]:
        self._ensure_service()
        try:
            results = (
                self._service.users()
                .messages()
                .list(userId=self.user_id, q=query, maxResults=max_results)
                .execute()
            )
            messages_meta = results.get("messages", [])
            if not messages_meta:
                return []

            parsed_emails: List[UnifiedEmail] = []
            for item in messages_meta:
                msg_id = item["id"]
                msg_detail = (
                    self._service.users()
                    .messages()
                    .get(userId=self.user_id, id=msg_id, format="full")
                    .execute()
                )
                unified_email = self.parse_gmail_message(msg_detail)
                parsed_emails.append(unified_email)

            return parsed_emails
        except HttpError as e:
            logger.error(f"Gmail API HTTP error while fetching messages: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching Gmail messages: {e}")
            raise

    def parse_gmail_message(self, raw_message: Dict[str, Any]) -> UnifiedEmail:
        """
        Decodes Gmail's payload structure into a standardized UnifiedEmail object.
        """
        msg_id = raw_message.get("id", "")
        thread_id = raw_message.get("threadId", "")
        label_ids = raw_message.get("labelIds", [])
        snippet = raw_message.get("snippet", "")
        
        payload = raw_message.get("payload", {})
        headers_list = payload.get("headers", [])
        
        headers_map: Dict[str, str] = {}
        for h in headers_list:
            headers_map[h.get("name", "").lower()] = h.get("value", "")

        subject = headers_map.get("subject", "(No Subject)")
        from_header = headers_map.get("from", "")
        to_header = headers_map.get("to", "")
        cc_header = headers_map.get("cc", "")
        date_header = headers_map.get("date", "")
        message_id_header = headers_map.get("message-id", None)
        in_reply_to = headers_map.get("in-reply-to", None)

        # Parse sender name and email
        sender_name, sender_email = email.utils.parseaddr(from_header)
        if not sender_email:
            sender_email = from_header

        # Parse recipients
        to_list = [addr[1] for addr in email.utils.getaddresses([to_header]) if addr[1]]
        cc_list = [addr[1] for addr in email.utils.getaddresses([cc_header]) if addr[1]]

        # Parse date
        parsed_date = datetime.now(timezone.utc)
        if date_header:
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_header)
            except Exception:
                pass

        # Extract text & html bodies and attachments recursively
        body_text, body_html, attachment_files = self._extract_payload_parts(payload)

        # Fallback to snippet if body text is empty
        if not body_text.strip():
            if body_html.strip():
                soup = BeautifulSoup(body_html, "html.parser")
                body_text = soup.get_text(separator="\n").strip()
            else:
                body_text = snippet

        return UnifiedEmail(
            id=msg_id,
            source=EmailSource.GMAIL,
            thread_id=thread_id,
            message_id_header=message_id_header,
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
            has_attachments=len(attachment_files) > 0,
            attachment_filenames=attachment_files,
            headers=headers_map,
            labels=label_ids,
            is_unread="UNREAD" in label_ids,
        )

    def _extract_payload_parts(self, part: Dict[str, Any]) -> tuple[str, str, List[str]]:
        """
        Recursively traverses MIME parts to extract plain text, HTML, and attachment filenames.
        """
        body_text = ""
        body_html = ""
        attachment_filenames: List[str] = []

        mime_type = part.get("mimeType", "")
        filename = part.get("filename", "")
        body_data = part.get("body", {}).get("data", None)

        if filename:
            attachment_filenames.append(filename)

        if body_data:
            try:
                decoded_bytes = base64.urlsafe_b64decode(body_data.encode("ASCII"))
                decoded_content = decoded_bytes.decode("utf-8", errors="replace")
                if mime_type == "text/plain":
                    body_text += decoded_content
                elif mime_type == "text/html":
                    body_html += decoded_content
            except Exception as e:
                logger.debug(f"Failed to decode body part: {e}")

        # Recurse child parts
        sub_parts = part.get("parts", [])
        for sub_part in sub_parts:
            sub_text, sub_html, sub_attachments = self._extract_payload_parts(sub_part)
            if sub_text:
                body_text += "\n" + sub_text
            if sub_html:
                body_html += "\n" + sub_html
            attachment_filenames.extend(sub_attachments)

        return body_text.strip(), body_html.strip(), attachment_filenames

    async def mark_as_read(self, msg_id: str):
        """Removes the UNREAD label from a message."""
        await asyncio.to_thread(self._modify_labels_sync, msg_id, remove_labels=["UNREAD"])

    async def add_labels(self, msg_id: str, label_names: List[str]):
        """Creates labels if they don't exist and applies them to the message."""
        await asyncio.to_thread(self._add_labels_sync, msg_id, label_names)

    def _modify_labels_sync(
        self,
        msg_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ):
        self._ensure_service()
        body = {
            "addLabelIds": add_labels or [],
            "removeLabelIds": remove_labels or [],
        }
        self._service.users().messages().modify(
            userId=self.user_id, id=msg_id, body=body
        ).execute()

    def _get_or_create_label_id(self, label_name: str) -> str:
        self._ensure_service()
        if not self._label_cache:
            res = self._service.users().labels().list(userId=self.user_id).execute()
            for lbl in res.get("labels", []):
                self._label_cache[lbl["name"]] = lbl["id"]

        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # Create new label
        try:
            created = (
                self._service.users()
                .labels()
                .create(
                    userId=self.user_id,
                    body={"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
                )
                .execute()
            )
            lbl_id = created["id"]
            self._label_cache[label_name] = lbl_id
            return lbl_id
        except HttpError as e:
            logger.warning(f"Label creation warning for '{label_name}': {e}")
            # Refresh cache in case created concurrently
            res = self._service.users().labels().list(userId=self.user_id).execute()
            for lbl in res.get("labels", []):
                self._label_cache[lbl["name"]] = lbl["id"]
            return self._label_cache.get(label_name, "")

    def _add_labels_sync(self, msg_id: str, label_names: List[str]):
        label_ids = [self._get_or_create_label_id(name) for name in label_names if name]
        label_ids = [lid for lid in label_ids if lid]
        if label_ids:
            self._modify_labels_sync(msg_id, add_labels=label_ids)
