"""
V.I.E.R.N.E.S Email Intelligence Models
Pydantic schemas for unified email representation, heuristic triage, and LLM structured output.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmailSource(str, Enum):
    GMAIL = "GMAIL"
    ZOHO_IMAP = "ZOHO_IMAP"
    GENERIC_IMAP = "GENERIC_IMAP"


class EmailCategory(str, Enum):
    CRITICAL = "CRITICAL"                    # Server down, security incident, legal notice, emergency
    IMPORTANT = "IMPORTANT"                  # High-value business, VIP sender, direct client query
    ACTION_REQUIRED = "ACTION_REQUIRED"      # Specific task, review, approval, question to answer
    FYI_TRANSACTIONAL = "FYI_TRANSACTIONAL"  # Invoices, receipts, 2FA/OTPs, system confirmations
    PROMOTIONAL = "PROMOTIONAL"              # Newsletters, marketing, sales pitches, discounts
    SPAM = "SPAM"                            # Phishing, unsolicited mass outreach, junk


class EmailPriority(int, Enum):
    P1_CRITICAL = 1  # Immediate notification (< 5 min)
    P2_HIGH = 2      # Alert in current working session (< 1 hour)
    P3_MEDIUM = 3    # Routine action items (same day)
    P4_LOW = 4       # Daily summary / digest
    P5_MINIMAL = 5   # Silently archived / skipped


class ActionItem(BaseModel):
    task: str = Field(description="Clear description of the action required")
    assignee: Optional[str] = Field(default=None, description="Person responsible if stated")
    deadline: Optional[str] = Field(default=None, description="Due date or time constraint if specified")


class UnifiedEmail(BaseModel):
    """
    Standardized email object agnostic of whether it originated from Gmail API or Zoho IMAP.
    """
    id: str = Field(description="Unique message identifier in source provider")
    source: EmailSource
    thread_id: Optional[str] = None
    message_id_header: Optional[str] = Field(default=None, description="RFC 822 Message-ID")
    in_reply_to: Optional[str] = None
    
    sender_name: Optional[str] = None
    sender_email: str
    recipient_emails: List[str] = Field(default_factory=list)
    cc_emails: List[str] = Field(default_factory=list)
    
    subject: str
    date: datetime
    
    body_text: str
    body_html: Optional[str] = None
    snippet: Optional[str] = None
    
    has_attachments: bool = False
    attachment_filenames: List[str] = Field(default_factory=list)
    
    # Raw email headers relevant for heuristic analysis
    headers: Dict[str, str] = Field(default_factory=dict)
    
    # Provider metadata
    labels: List[str] = Field(default_factory=list)
    is_unread: bool = True


class HeuristicEvaluation(BaseModel):
    """
    Result of fast Tier-1 deterministic heuristics.
    """
    is_definitive: bool = Field(
        default=False, 
        description="True if heuristics are confident enough to bypass LLM (e.g. obvious newsletter or spam)"
    )
    predicted_category: Optional[EmailCategory] = None
    predicted_priority: Optional[EmailPriority] = None
    heuristic_score: float = Field(
        default=0.0, 
        description="Score between -10.0 (Definite Spam/Promo) and +10.0 (VIP/Emergency)"
    )
    reasons: List[str] = Field(default_factory=list)
    is_vip: bool = False
    has_unsubscribe_header: bool = False
    is_auto_submitted: bool = False


class LLMTriageOutput(BaseModel):
    """
    Structured output extracted by the LLM in Tier-2 semantic analysis.
    """
    category: EmailCategory = Field(
        description="Categorization of the email into CRITICAL, IMPORTANT, ACTION_REQUIRED, FYI_TRANSACTIONAL, PROMOTIONAL, or SPAM"
    )
    priority: EmailPriority = Field(
        description="Priority level from P1_CRITICAL (1) to P5_MINIMAL (5)"
    )
    urgency_reasoning: str = Field(
        description="Brief 1-sentence justification for the assigned priority and category"
    )
    executive_summary: str = Field(
        description="1 to 2 sentence high-level executive briefing summarizing the core message"
    )
    action_items: List[ActionItem] = Field(
        default_factory=list, 
        description="Concrete tasks requested in the email, including assignees and deadlines"
    )
    deadline: Optional[str] = Field(
        default=None, 
        description="Any critical date or deadline mentioned in the email"
    )
    suggested_reply: Optional[str] = Field(
        default=None, 
        description="A concise, professional draft response ready for user approval if a response is needed"
    )
    requires_immediate_push: bool = Field(
        default=False, 
        description="True if V.I.E.R.N.E.S should interrupt the user immediately with an alert"
    )


class EmailTriageResult(BaseModel):
    """
    Final composite result for an email after running through Tier 1 (Heuristic) and Tier 2 (LLM).
    """
    email_id: str
    source: EmailSource
    subject: str
    sender_email: str
    sender_name: Optional[str] = None
    date: datetime
    
    category: EmailCategory
    priority: EmailPriority
    executive_summary: str
    urgency_reasoning: str
    action_items: List[ActionItem] = Field(default_factory=list)
    deadline: Optional[str] = None
    suggested_reply: Optional[str] = None
    requires_immediate_push: bool = False
    
    processed_via_llm: bool = True
    heuristic_reasons: List[str] = Field(default_factory=list)
    
    suggested_labels: List[str] = Field(default_factory=list)
    timestamp_processed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
