"""
V.I.E.R.N.E.S Email Intelligence Module
"""
from src.email_intelligence.models import (
    ActionItem,
    EmailCategory,
    EmailPriority,
    EmailSource,
    EmailTriageResult,
    UnifiedEmail,
)
from src.email_intelligence.gmail_service import GmailService
from src.email_intelligence.zoho_imap_service import ZohoIMAPService
from src.email_intelligence.heuristic_filter import HeuristicFilter
from src.email_intelligence.llm_classifier import LLMClassifier
from src.email_intelligence.orchestrator import EmailIntelligenceOrchestrator

__all__ = [
    "ActionItem",
    "EmailCategory",
    "EmailPriority",
    "EmailSource",
    "EmailTriageResult",
    "UnifiedEmail",
    "GmailService",
    "ZohoIMAPService",
    "HeuristicFilter",
    "LLMClassifier",
    "EmailIntelligenceOrchestrator",
]
