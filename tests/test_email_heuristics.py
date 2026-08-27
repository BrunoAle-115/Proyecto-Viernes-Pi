import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
import unittest

from src.email_intelligence.heuristic_filter import HeuristicFilter
from src.email_intelligence.models import (
    EmailCategory,
    EmailPriority,
    EmailSource,
    UnifiedEmail,
)


class TestEmailHeuristics(unittest.TestCase):
    def setUp(self):
        self.heuristic_filter = HeuristicFilter(
            vip_senders=["vip_executive@partner.com", "ceo@company.com"],
            vip_domains=["company.com", "bigclient.com"],
            urgent_keywords=["urgent", "outage", "sev-1", "emergency"],
        )

    def test_newsletter_detection_via_list_unsubscribe(self):
        email = UnifiedEmail(
            id="em-1",
            source=EmailSource.GMAIL,
            sender_email="newsletter@cloudweekly.com",
            subject="Issue #42: Modern Python Tips",
            date=datetime.now(timezone.utc),
            body_text="Here are this week's top Python tips. Click here to unsubscribe.",
            headers={
                "list-unsubscribe": "<https://cloudweekly.com/unsub>",
                "precedence": "bulk",
            },
        )
        res = self.heuristic_filter.evaluate(email)
        self.assertTrue(res.is_definitive)
        self.assertEqual(res.predicted_category, EmailCategory.PROMOTIONAL)
        self.assertEqual(res.predicted_priority, EmailPriority.P5_MINIMAL)
        self.assertLessEqual(res.heuristic_score, -5.0)

    def test_upstream_spam_flag(self):
        email = UnifiedEmail(
            id="em-2",
            source=EmailSource.ZOHO_IMAP,
            sender_email="random@unknown-spammer.xyz",
            subject="Get rich quick with this one crypto trick",
            date=datetime.now(timezone.utc),
            body_text="Earn 5000% APR today guaranteed.",
            headers={"x-spam-flag": "YES"},
        )
        res = self.heuristic_filter.evaluate(email)
        self.assertTrue(res.is_definitive)
        self.assertEqual(res.predicted_category, EmailCategory.SPAM)
        self.assertEqual(res.predicted_priority, EmailPriority.P5_MINIMAL)

    def test_2fa_otp_detection(self):
        email = UnifiedEmail(
            id="em-3",
            source=EmailSource.GMAIL,
            sender_email="no-reply@auth0.com",
            subject="Your login verification code is 491023",
            date=datetime.now(timezone.utc),
            body_text="Your verification code is 491023. Valid for 10 minutes.",
            headers={"auto-submitted": "auto-generated"},
        )
        res = self.heuristic_filter.evaluate(email)
        self.assertTrue(res.is_definitive)
        self.assertEqual(res.predicted_category, EmailCategory.FYI_TRANSACTIONAL)
        self.assertEqual(res.predicted_priority, EmailPriority.P2_HIGH)

    def test_vip_urgent_sender_routes_to_llm(self):
        email = UnifiedEmail(
            id="em-4",
            source=EmailSource.GMAIL,
            sender_email="ceo@company.com",
            subject="URGENT: Need board deck update",
            date=datetime.now(timezone.utc),
            body_text="Please update slide 4 with the latest ARR numbers before tomorrow 9 AM.",
            headers={},
        )
        res = self.heuristic_filter.evaluate(email)
        # VIP should not be short-circuited as spam; it requires semantic extraction
        self.assertFalse(res.is_definitive)
        self.assertTrue(res.is_vip)
        self.assertGreaterEqual(res.heuristic_score, 10.0)
        self.assertEqual(res.predicted_priority, EmailPriority.P1_CRITICAL)


if __name__ == "__main__":
    unittest.main()
