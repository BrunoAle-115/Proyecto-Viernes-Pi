"""
V.I.E.R.N.E.S Email Intelligence Orchestrator
Coordinates multi-channel email fetching (Gmail + Zoho), 2-tier filtering, labeling, and dispatch.
"""

import asyncio
import logging
from typing import List, Optional

from src.email_intelligence.gmail_service import GmailService
from src.email_intelligence.heuristic_filter import HeuristicFilter
from src.email_intelligence.llm_classifier import LLMClassifier
from src.email_intelligence.models import (
    EmailCategory,
    EmailPriority,
    EmailTriageResult,
    UnifiedEmail,
)
from src.email_intelligence.zoho_imap_service import ZohoIMAPService

logger = logging.getLogger("VIERNES.EmailOrchestrator")


class EmailIntelligenceOrchestrator:
    """
    Main pipeline controller for email intelligence in V.I.E.R.N.E.S.
    """

    def __init__(
        self,
        gmail_service: Optional[GmailService] = None,
        zoho_service: Optional[ZohoIMAPService] = None,
        heuristic_filter: Optional[HeuristicFilter] = None,
        llm_classifier: Optional[LLMClassifier] = None,
    ):
        self.gmail = gmail_service or GmailService()
        self.zoho = zoho_service or ZohoIMAPService()
        self.heuristics = heuristic_filter or HeuristicFilter()
        self.llm = llm_classifier or LLMClassifier()

    async def process_single_email(self, email_obj: UnifiedEmail) -> EmailTriageResult:
        """
        Executes 2-tier analysis on a single incoming email.
        """
        logger.info(f"Processing email [{email_obj.source.value}] from '{email_obj.sender_email}': '{email_obj.subject}'")

        # Tier 1: Deterministic Heuristic Pre-Filtering
        h_eval = self.heuristics.evaluate(email_obj)

        if h_eval.is_definitive and h_eval.predicted_category:
            # Definite Promo, Spam, or simple OTP -> Skip LLM
            logger.info(
                f"-> Short-circuit via Tier-1 Heuristics: Category={h_eval.predicted_category.value}, "
                f"Score={h_eval.heuristic_score:.1f}, Reasons={'; '.join(h_eval.reasons)}"
            )

            # Produce concise summary without LLM costs
            summary = f"Automated {h_eval.predicted_category.value.lower()} from {email_obj.sender_email}: {email_obj.subject}"
            if h_eval.predicted_category == EmailCategory.FYI_TRANSACTIONAL:
                summary = f"Transactional message ({email_obj.subject}) from {email_obj.sender_email}."

            triage_result = EmailTriageResult(
                email_id=email_obj.id,
                source=email_obj.source,
                subject=email_obj.subject,
                sender_email=email_obj.sender_email,
                sender_name=email_obj.sender_name,
                date=email_obj.date,
                category=h_eval.predicted_category,
                priority=h_eval.predicted_priority or EmailPriority.P5_MINIMAL,
                executive_summary=summary,
                urgency_reasoning=f"Heuristic determination (Score: {h_eval.heuristic_score:.1f}). " + "; ".join(h_eval.reasons),
                action_items=[],
                deadline=None,
                suggested_reply=None,
                requires_immediate_push=(h_eval.predicted_priority == EmailPriority.P1_CRITICAL),
                processed_via_llm=False,
                heuristic_reasons=h_eval.reasons,
                suggested_labels=[f"VIERNES/{h_eval.predicted_category.value}"],
            )
            return triage_result

        # Tier 2: Semantic LLM Analysis
        logger.info(f"-> Routing to Tier-2 LLM Classifier (Heuristic score: {h_eval.heuristic_score:.1f})")
        llm_out = await self.llm.classify(email_obj, heuristic_eval=h_eval)

        # Build labels
        labels = [
            f"VIERNES/{llm_out.category.value}",
            f"VIERNES/PRIORITY_P{llm_out.priority.value}",
        ]
        if llm_out.requires_immediate_push:
            labels.append("VIERNES/URGENT_PUSH")

        triage_result = EmailTriageResult(
            email_id=email_obj.id,
            source=email_obj.source,
            subject=email_obj.subject,
            sender_email=email_obj.sender_email,
            sender_name=email_obj.sender_name,
            date=email_obj.date,
            category=llm_out.category,
            priority=llm_out.priority,
            executive_summary=llm_out.executive_summary,
            urgency_reasoning=llm_out.urgency_reasoning,
            action_items=llm_out.action_items,
            deadline=llm_out.deadline,
            suggested_reply=llm_out.suggested_reply,
            requires_immediate_push=llm_out.requires_immediate_push,
            processed_via_llm=True,
            heuristic_reasons=h_eval.reasons,
            suggested_labels=labels,
        )

        return triage_result

    async def sync_and_triage_all(self) -> List[EmailTriageResult]:
        """
        Fetches unread emails from all configured providers, processes them concurrently,
        and applies labels where supported.
        """
        all_emails: List[UnifiedEmail] = []

        # 1. Fetch Gmail
        try:
            gmail_emails = await self.gmail.fetch_unread_messages(max_results=20)
            all_emails.extend(gmail_emails)
            logger.info(f"Fetched {len(gmail_emails)} unread messages from Gmail.")
        except Exception as e:
            logger.warning(f"Gmail fetch skipped or encountered error: {e}")

        # 2. Fetch Zoho Mail
        try:
            zoho_emails = await self.zoho.fetch_unread_messages(limit=20)
            all_emails.extend(zoho_emails)
            logger.info(f"Fetched {len(zoho_emails)} unread messages from Zoho IMAP.")
        except Exception as e:
            logger.warning(f"Zoho IMAP fetch skipped or encountered error: {e}")

        if not all_emails:
            logger.info("No unread emails found across mailboxes.")
            return []

        # 3. Process concurrently
        tasks = [self.process_single_email(em) for em in all_emails]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_results: List[EmailTriageResult] = []
        for em, res in zip(all_emails, results):
            if isinstance(res, Exception):
                logger.error(f"Error processing email {em.id}: {res}")
            else:
                successful_results.append(res)
                # Apply labels to Gmail if relevant
                if em.source == EmailSource.GMAIL and res.suggested_labels:
                    try:
                        await self.gmail.add_labels(em.id, res.suggested_labels)
                    except Exception as e:
                        logger.debug(f"Could not apply Gmail labels: {e}")

        return successful_results
