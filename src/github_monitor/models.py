"""
V.I.E.R.N.E.S GitHub PR Monitor Data Models
Defines Pydantic schemas for Pull Requests, Reviews, CI checks, and state transitions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ReviewState(str, Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class CIStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PENDING = "PENDING"
    NEUTRAL = "NEUTRAL"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class MergeableState(str, Enum):
    CLEAN = "CLEAN"        # Ready to merge
    DIRTY = "DIRTY"        # Has merge conflicts
    BLOCKED = "BLOCKED"    # Blocked by missing approvals or failing checks
    BEHIND = "BEHIND"      # Branch is behind base
    DRAFT = "DRAFT"        # Draft PR
    UNKNOWN = "UNKNOWN"


class ReviewDetail(BaseModel):
    reviewer: str
    state: ReviewState
    submitted_at: Optional[datetime] = None
    body: Optional[str] = None
    html_url: Optional[str] = None


class CheckRunDetail(BaseModel):
    name: str
    status: str       # queued, in_progress, completed
    conclusion: Optional[str] = None  # success, failure, neutral, timed_out, action_required
    html_url: Optional[str] = None


class PullRequestSnapshot(BaseModel):
    repository: str
    number: int
    title: str
    author: str
    html_url: str
    head_branch: str
    base_branch: str
    head_sha: str
    is_draft: bool = False
    
    # Review & CI Status
    review_decision: Optional[str] = Field(
        default=None, 
        description="Overall GitHub decision: APPROVED, CHANGES_REQUESTED, or REVIEW_REQUIRED"
    )
    reviews: List[ReviewDetail] = Field(default_factory=list)
    requested_reviewers: List[str] = Field(default_factory=list)
    
    ci_status: CIStatus = CIStatus.UNKNOWN
    failing_checks: List[str] = Field(default_factory=list)
    
    mergeable: Optional[bool] = None
    mergeable_state: MergeableState = MergeableState.UNKNOWN
    
    updated_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PRChangeType(str, Enum):
    PR_APPROVED = "PR_APPROVED"
    PR_CHANGES_REQUESTED = "PR_CHANGES_REQUESTED"
    PR_NEW_COMMENT = "PR_NEW_COMMENT"
    PR_CI_FAILED = "PR_CI_FAILED"
    PR_CI_PASSED = "PR_CI_PASSED"
    PR_MERGE_CONFLICT = "PR_MERGE_CONFLICT"
    PR_REVIEW_REQUESTED = "PR_REVIEW_REQUESTED"
    PR_READY_FOR_MERGE = "PR_READY_FOR_MERGE"


class PRAlertEvent(BaseModel):
    event_type: PRChangeType
    repository: str
    pr_number: int
    pr_title: str
    pr_url: str
    actor: str  # Reviewer or system who caused the event
    
    headline: str
    details: str
    action_required: bool = True
    suggested_action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
