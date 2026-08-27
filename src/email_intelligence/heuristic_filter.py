"""
V.I.E.R.N.E.S Tier-1 Deterministic Email Heuristic Filter
Performs zero-cost, millisecond-speed pre-filtering based on RFC headers, ESP fingerprints,
VIP lists, transactional regex patterns, and promotional indicators.
"""

import re
from typing import List, Tuple
from src.config import settings
from src.email_intelligence.models import (
    EmailCategory,
    EmailPriority,
    HeuristicEvaluation,
    UnifiedEmail,
)


class HeuristicFilter:
    """
    Evaluates incoming emails deterministically without calling LLMs.
    Eliminates >70% of promotional, newsletter, and automated spam tokens.
    """

    def __init__(
        self,
        vip_senders: List[str] = settings.VIP_SENDERS,
        vip_domains: List[str] = settings.VIP_DOMAINS,
        urgent_keywords: List[str] = settings.URGENT_KEYWORDS,
    ):
        self.vip_senders = {s.lower() for s in vip_senders}
        self.vip_domains = {d.lower() for d in vip_domains}
        self.urgent_keywords = urgent_keywords

        # Compiled regex patterns for speed
        self._otp_pattern = re.compile(
            r"\b(verification\s*code|security\s*code|código\s*de\s*verificación|one-time\s*password|otp|2fa|login\s*code|two-factor)\b",
            re.IGNORECASE,
        )
        self._invoice_receipt_pattern = re.compile(
            r"\b(invoice|receipt|factura|recibo|payment\s*confirmation|order\s*confirmation|comprobante\s*de\s*pago|billing\s*statement)\b",
            re.IGNORECASE,
        )
        self._promo_text_pattern = re.compile(
            r"\b(unsubscribe|desuscribirse|view\s*in\s*browser|ver\s*en\s*el\s*navegador|special\s*offer|limited\s*time|discount|\d+%\s*off|promo\s*code|black\s*friday|cyber\s*monday)\b",
            re.IGNORECASE,
        )
        self._cloud_alert_pattern = re.compile(
            r"\b(aws\s*budget|google\s*cloud\s*alert|azure\s*alert|sentry\s*issue|datadog\s*alert|grafana\s*alert|uptime\s*robot|pagerduty)\b",
            re.IGNORECASE,
        )

    def evaluate(self, email_obj: UnifiedEmail) -> HeuristicEvaluation:
        score = 0.0
        reasons: List[str] = []
        is_vip = False
        has_unsubscribe = False
        is_auto_submitted = False

        headers = email_obj.headers
        sender_email = email_obj.sender_email.lower()
        sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
        subject = email_obj.subject.lower()
        body_sample = email_obj.body_text[:2000].lower()

        # -------------------------------------------------------------
        # 1. VIP & Whitelist Checks (Strong Positive Score)
        # -------------------------------------------------------------
        if sender_email in self.vip_senders:
            score += 8.0
            is_vip = True
            reasons.append(f"Sender {sender_email} is in VIP sender whitelist (+8.0)")

        elif any(sender_domain == d or sender_domain.endswith("." + d) for d in self.vip_domains):
            score += 5.0
            is_vip = True
            reasons.append(f"Sender domain {sender_domain} matches VIP domain whitelist (+5.0)")

        # -------------------------------------------------------------
        # 2. Urgent Keyword Signals in Subject
        # -------------------------------------------------------------
        for kw in self.urgent_keywords:
            if kw in subject:
                score += 4.5
                reasons.append(f"Subject contains urgent keyword: '{kw}' (+4.5)")
                break

        # -------------------------------------------------------------
        # 3. RFC & ESP Newsletter/Bulk Headers (Strong Negative Score)
        # -------------------------------------------------------------
        # List-Unsubscribe is the gold standard for bulk/marketing mail
        if "list-unsubscribe" in headers or "list-id" in headers or "list-post" in headers:
            has_unsubscribe = True
            score -= 5.5
            reasons.append("Contains RFC List-Unsubscribe / List-Id headers (-5.5)")

        # Precedence: bulk / list / junk
        precedence = headers.get("precedence", "").lower()
        if precedence in ["bulk", "list", "junk"]:
            score -= 4.0
            reasons.append(f"Precedence header is '{precedence}' (-4.0)")

        # Auto-Submitted
        auto_sub = headers.get("auto-submitted", "").lower()
        if auto_sub and auto_sub != "no":
            is_auto_submitted = True
            reasons.append(f"Auto-Submitted header detected: '{auto_sub}'")

        # ESP Marketing fingerprints (Mailchimp, SendGrid marketing, HubSpot, Marketo, etc.)
        esp_markers = [
            "x-campaign", "x-campaign-id", "x-mktg-id", "x-sendgrid-eid",
            "x-mailgun-tag", "x-hubspot-messages", "x-marketo-id", "feedback-id"
        ]
        found_esp = [m for m in esp_markers if m in headers]
        if found_esp:
            score -= 3.5
            reasons.append(f"Detected marketing ESP header: {found_esp[0]} (-3.5)")

        # Spam headers injected by mail filters
        if headers.get("x-spam-flag", "").upper() == "YES" or "status=spam" in headers.get("x-spam-status", "").lower():
            score -= 8.0
            reasons.append("Upstream spam flag detected (X-Spam-Flag: YES) (-8.0)")

        # -------------------------------------------------------------
        # 4. Sender Address Pattern Checks
        # -------------------------------------------------------------
        marketing_senders = ["newsletter@", "marketing@", "news@", "promo@", "deals@", "digest@", "info@"]
        if any(sender_email.startswith(m) for m in marketing_senders):
            score -= 4.0
            reasons.append(f"Sender address starts with promotional prefix '{sender_email}' (-4.0)")

        # -------------------------------------------------------------
        # 5. Transactional & OTP Detection
        # -------------------------------------------------------------
        if self._otp_pattern.search(subject) or self._otp_pattern.search(body_sample[:500]):
            score += 3.0
            reasons.append("Detected 2FA / OTP verification security code pattern")
            # If it's pure 2FA, it's definitive transactional FYI
            return HeuristicEvaluation(
                is_definitive=True,
                predicted_category=EmailCategory.FYI_TRANSACTIONAL,
                predicted_priority=EmailPriority.P2_HIGH,
                heuristic_score=score,
                reasons=reasons,
                is_vip=is_vip,
                has_unsubscribe_header=has_unsubscribe,
                is_auto_submitted=is_auto_submitted,
            )

        if self._invoice_receipt_pattern.search(subject):
            score += 1.0
            reasons.append("Detected invoice/receipt transactional pattern")
            if has_unsubscribe:
                # E.g. automated receipt from SaaS with list unsubscribe
                return HeuristicEvaluation(
                    is_definitive=True,
                    predicted_category=EmailCategory.FYI_TRANSACTIONAL,
                    predicted_priority=EmailPriority.P4_LOW,
                    heuristic_score=score,
                    reasons=reasons,
                    is_vip=is_vip,
                    has_unsubscribe_header=has_unsubscribe,
                    is_auto_submitted=is_auto_submitted,
                )

        if self._cloud_alert_pattern.search(subject):
            score += 4.0
            reasons.append("Detected infrastructure monitoring alert (AWS/GCP/Sentry/Datadog)")
            return HeuristicEvaluation(
                is_definitive=False,  # Let LLM assess severity of alert
                predicted_category=EmailCategory.CRITICAL,
                predicted_priority=EmailPriority.P1_CRITICAL,
                heuristic_score=score,
                reasons=reasons,
                is_vip=is_vip,
                has_unsubscribe_header=has_unsubscribe,
                is_auto_submitted=is_auto_submitted,
            )

        # -------------------------------------------------------------
        # 6. Body Keyword Checks (Promo vs Action)
        # -------------------------------------------------------------
        if self._promo_text_pattern.search(body_sample) and not is_vip:
            score -= 2.0
            reasons.append("Email body contains promotional or unsubscribe phrase (-2.0)")

        # -------------------------------------------------------------
        # 7. Decision Synthesis
        # -------------------------------------------------------------
        # A) Definite Spam / Marketing: Highly negative score and not a VIP
        if score <= -5.0 and not is_vip:
            return HeuristicEvaluation(
                is_definitive=True,
                predicted_category=EmailCategory.PROMOTIONAL if has_unsubscribe else EmailCategory.SPAM,
                predicted_priority=EmailPriority.P5_MINIMAL,
                heuristic_score=score,
                reasons=reasons,
                is_vip=is_vip,
                has_unsubscribe_header=has_unsubscribe,
                is_auto_submitted=is_auto_submitted,
            )

        # B) Non-definitive or Potentially Important / Ambiguous -> Dispatch to LLM
        predicted_cat = EmailCategory.IMPORTANT if score >= 4.0 else EmailCategory.ACTION_REQUIRED
        predicted_pri = (
            EmailPriority.P1_CRITICAL if score >= 7.0
            else EmailPriority.P2_HIGH if score >= 4.0
            else EmailPriority.P3_MEDIUM
        )

        return HeuristicEvaluation(
            is_definitive=False,
            predicted_category=predicted_cat,
            predicted_priority=predicted_pri,
            heuristic_score=score,
            reasons=reasons,
            is_vip=is_vip,
            has_unsubscribe_header=has_unsubscribe,
            is_auto_submitted=is_auto_submitted,
        )
