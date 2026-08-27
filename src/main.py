"""
V.I.E.R.N.E.S Main Entrypoint & Demonstration Suite
Runs Email Intelligence and GitHub PR Monitoring in either live daemon mode or simulation test mode.
"""

import asyncio
from datetime import datetime, timezone
import logging
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import settings
from src.email_intelligence.heuristic_filter import HeuristicFilter
from src.email_intelligence.llm_classifier import LLMClassifier
from src.email_intelligence.models import (
    EmailCategory,
    EmailPriority,
    EmailSource,
    UnifiedEmail,
)
from src.email_intelligence.orchestrator import EmailIntelligenceOrchestrator
from src.github_monitor.models import (
    CIStatus,
    MergeableState,
    PRAlertEvent,
    PullRequestSnapshot,
    ReviewDetail,
    ReviewState,
)
from src.github_monitor.pr_monitor import PullRequestMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("VIERNES.Main")


async def run_email_intelligence_demo():
    print("\n" + "=" * 70)
    print("🤖 V.I.E.R.N.E.S: EMAIL INTELLIGENCE SIMULATION PIPELINE")
    print("=" * 70 + "\n")

    orchestrator = EmailIntelligenceOrchestrator(
        heuristic_filter=HeuristicFilter(),
        llm_classifier=LLMClassifier(),
    )

    # Simulated batch of emails covering all real-world scenarios
    sample_emails = [
        # 1. Critical Production Emergency
        UnifiedEmail(
            id="msg-001",
            source=EmailSource.GMAIL,
            sender_name="Sarah Connor (VP Eng)",
            sender_email="sarah.connor@client-corp.com",
            recipient_emails=["user@company.com"],
            subject="URGENT: Production Gateway 500 Outage",
            date=datetime.now(timezone.utc),
            body_text="Hi Team, our production payment gateway has been returning 500 Internal Server Errors since 18:00 UTC. Customers cannot checkout. Please join the incident bridge immediately: https://meet.google.com/xyz",
            headers={"message-id": "<outage-001@client-corp.com>"},
        ),
        # 2. VIP Business Contract Review
        UnifiedEmail(
            id="msg-002",
            source=EmailSource.ZOHO_IMAP,
            sender_name="Arthur CEO",
            sender_email="ceo@company.com",
            recipient_emails=["user@company.com"],
            subject="Please review Q4 Enterprise expansion term sheet",
            date=datetime.now(timezone.utc),
            body_text="Hey, please review the attached revised expansion term sheet with Partner Corp. We need your feedback on clause 4 (IP ownership) before Thursday 4 PM so legal can sign.",
            has_attachments=True,
            attachment_filenames=["Q4_Expansion_TermSheet_v2.pdf"],
            headers={"message-id": "<ceo-002@company.com>"},
        ),
        # 3. 2FA Security Code (Definite Transactional FYI)
        UnifiedEmail(
            id="msg-003",
            source=EmailSource.GMAIL,
            sender_name="GitHub Security",
            sender_email="noreply@github.com",
            recipient_emails=["user@company.com"],
            subject="Your GitHub verification code is 849201",
            date=datetime.now(timezone.utc),
            body_text="Verification code: 849201. Please enter this code within 10 minutes to complete your device authentication.",
            headers={"auto-submitted": "auto-generated"},
        ),
        # 4. Marketing Newsletter (Definite Promo via List-Unsubscribe Header)
        UnifiedEmail(
            id="msg-004",
            source=EmailSource.GMAIL,
            sender_name="Tech Digest",
            sender_email="news@techdigest-weekly.io",
            recipient_emails=["user@company.com"],
            subject="Top 10 Software Architecture Patterns for 2026",
            date=datetime.now(timezone.utc),
            body_text="Read our curated list of distributed systems patterns. Upgrade your subscription today for 40% off with coupon CODE2026. Click unsubscribe to opt-out.",
            headers={
                "list-unsubscribe": "<mailto:unsub@techdigest-weekly.io>",
                "precedence": "bulk",
                "x-campaign-id": "camp_98241",
            },
        ),
        # 5. Cold Spam / Unsolicited Pitch
        UnifiedEmail(
            id="msg-005",
            source=EmailSource.ZOHO_IMAP,
            sender_name="Lead Gen Solutions",
            sender_email="spammer@outreach-boost-growth.biz",
            recipient_emails=["user@company.com"],
            subject="We can 10x your B2B sales pipeline overnight",
            date=datetime.now(timezone.utc),
            body_text="Dear Founder, we offer high-volume email blasting services for $99. Reply back if interested in buying our database of 500k leads.",
            headers={"x-spam-flag": "YES"},
        ),
    ]

    for idx, email_obj in enumerate(sample_emails, 1):
        res = await orchestrator.process_single_email(email_obj)
        engine_label = "Tier-2 LLM Classifier" if res.processed_via_llm else "Tier-1 Deterministic Heuristic"
        print(f"[{idx}] {res.category.value} | Priority: P{res.priority.value} ({res.priority.name}) | Engine: {engine_label}")
        print(f"    From: {res.sender_name or ''} <{res.sender_email}>")
        print(f"    Subject: {res.subject}")
        print(f"    Executive Summary: {res.executive_summary}")
        if res.action_items:
            for act in res.action_items:
                print(f"    ⚡ Action: {act.task} [Deadline: {act.deadline or 'None'}]")
        if res.suggested_reply:
            print(f"    💬 Suggested Reply: \"{res.suggested_reply}\"")
        print(f"    🏷️  Labels: {', '.join(res.suggested_labels)}")
        print(f"    🚨 Immediate Push: {res.requires_immediate_push}")
        print("-" * 70)


async def run_github_monitor_demo():
    print("\n" + "=" * 70)
    print("🐙 V.I.E.R.N.E.S: GITHUB PR & REVIEW MONITOR SIMULATION")
    print("=" * 70 + "\n")

    monitor = PullRequestMonitor()

    # Step 1: Initial state (PR submitted, pending review)
    pr_t0 = PullRequestSnapshot(
        repository="enterprise/core-engine",
        number=142,
        title="feat: Add OAuth2 token auto-refresh and resilience circuit breaker",
        author="bruno",
        html_url="https://github.com/enterprise/core-engine/pull/142",
        head_branch="feature/oauth2-resilience",
        base_branch="main",
        head_sha="sha_commit_001",
        review_decision="REVIEW_REQUIRED",
        reviews=[],
        ci_status=CIStatus.PENDING,
        mergeable_state=MergeableState.CLEAN,
        updated_at=datetime.now(timezone.utc),
    )
    print("[Cycle 1] Polling PR #142 (Newly created, awaiting review & CI)...")
    alerts_0 = monitor.evaluate_snapshot(pr_t0)
    print(f"-> Alerts triggered: {len(alerts_0)}")

    # Step 2: Reviewer requests changes
    pr_t1 = pr_t0.model_copy(deep=True)
    pr_t1.reviews = [
        ReviewDetail(
            reviewer="senior_architect",
            state=ReviewState.CHANGES_REQUESTED,
            body="Please handle the edge case where the refresh token endpoint returns 400 invalid_grant. Add unit test for retry limits.",
            html_url="https://github.com/enterprise/core-engine/pull/142#pullrequestreview-9812",
        )
    ]
    pr_t1.review_decision = "CHANGES_REQUESTED"
    pr_t1.ci_status = CIStatus.SUCCESS

    print("\n[Cycle 2] Polling PR #142 after Senior Architect reviews...")
    alerts_1 = monitor.evaluate_snapshot(pr_t1)
    for a in alerts_1:
        print(f"\n🔔 ALERT: {a.headline}")
        print(f"   Details: {a.details}")
        print(f"   Action:  {a.suggested_action}")
        print(f"   URL:     {a.pr_url}")

    # Step 3: Developer fixes issues, pushes new commit, and reviewer approves
    pr_t2 = pr_t1.model_copy(deep=True)
    pr_t2.head_sha = "sha_commit_002"
    pr_t2.reviews = [
        ReviewDetail(
            reviewer="senior_architect",
            state=ReviewState.APPROVED,
            body="Looks great! Thanks for addressing the 400 invalid_grant handling.",
            html_url="https://github.com/enterprise/core-engine/pull/142#pullrequestreview-9890",
        )
    ]
    pr_t2.review_decision = "APPROVED"
    pr_t2.ci_status = CIStatus.SUCCESS
    pr_t2.mergeable_state = MergeableState.CLEAN

    print("\n[Cycle 3] Polling PR #142 after developer pushes fix and architect re-reviews...")
    alerts_2 = monitor.evaluate_snapshot(pr_t2)
    for a in alerts_2:
        print(f"\n🔔 ALERT: {a.headline}")
        print(f"   Details: {a.details}")
        print(f"   Action:  {a.suggested_action}")
        print(f"   URL:     {a.pr_url}")

    print("\n" + "=" * 70 + "\n")


async def main():
    await run_email_intelligence_demo()
    await run_github_monitor_demo()


if __name__ == "__main__":
    asyncio.run(main())
