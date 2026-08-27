"""
V.I.E.R.N.E.S Configuration Settings
Manages environment variables, secrets, credentials paths, and system parameters with zero external dependencies.
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field

# Try importing dotenv if installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings(BaseModel):
    # App General Settings
    APP_NAME: str = "V.I.E.R.N.E.S Email & GitHub Intelligence"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # AI / LLM Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "gemini-2.5-flash")

    # Gmail API (OAuth2)
    GMAIL_CREDENTIALS_FILE: str = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials/gmail_credentials.json")
    GMAIL_TOKEN_FILE: str = os.getenv("GMAIL_TOKEN_FILE", "credentials/gmail_token.json")
    GMAIL_SCOPES: List[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.labels",
        ]
    )
    GMAIL_USER_ID: str = os.getenv("GMAIL_USER_ID", "me")
    GMAIL_POLL_INTERVAL_SECONDS: int = int(os.getenv("GMAIL_POLL_INTERVAL_SECONDS", "60"))

    # Zoho Mail (IMAP)
    ZOHO_IMAP_SERVER: str = os.getenv("ZOHO_IMAP_SERVER", "imap.zoho.com")
    ZOHO_IMAP_PORT: int = int(os.getenv("ZOHO_IMAP_PORT", "993"))
    ZOHO_IMAP_USE_SSL: bool = os.getenv("ZOHO_IMAP_USE_SSL", "true").lower() == "true"
    ZOHO_EMAIL_USER: Optional[str] = os.getenv("ZOHO_EMAIL_USER")
    ZOHO_EMAIL_PASSWORD: Optional[str] = os.getenv("ZOHO_EMAIL_PASSWORD")  # App-specific password
    ZOHO_POLL_INTERVAL_SECONDS: int = int(os.getenv("ZOHO_POLL_INTERVAL_SECONDS", "60"))
    ZOHO_IDLE_TIMEOUT_SECONDS: int = int(os.getenv("ZOHO_IDLE_TIMEOUT_SECONDS", "300"))

    # Email Intelligence Heuristic Configuration
    VIP_SENDERS: List[str] = Field(
        default_factory=lambda: [
            "ceo@company.com",
            "cto@company.com",
            "founder@company.com",
            "legal@company.com",
            "investors@company.com",
        ]
    )
    VIP_DOMAINS: List[str] = Field(
        default_factory=lambda: [
            "company.com",
            "client-corp.com",
            "investorfund.vc",
        ]
    )
    URGENT_KEYWORDS: List[str] = Field(
        default_factory=lambda: [
            "urgent",
            "asap",
            "emergency",
            "critical",
            "sev1",
            "sev-1",
            "outage",
            "security breach",
            "incident",
            "deadline today",
            "action required immediately",
        ]
    )

    # GitHub Monitor Configuration
    GITHUB_ACCESS_TOKEN: Optional[str] = os.getenv("GITHUB_ACCESS_TOKEN")
    GITHUB_REPOSITORIES: List[str] = Field(
        default_factory=lambda: [
            "org-name/repo-core",
            "org-name/repo-frontend",
            "org-name/repo-backend",
        ]
    )
    GITHUB_POLL_INTERVAL_SECONDS: int = int(os.getenv("GITHUB_POLL_INTERVAL_SECONDS", "120"))


settings = Settings()
