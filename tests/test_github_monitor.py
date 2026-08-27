import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
import unittest

from src.github_monitor.models import (
    CIStatus,
    MergeableState,
    PRChangeType,
    PullRequestSnapshot,
    ReviewDetail,
    ReviewState,
)
from src.github_monitor.pr_monitor import PullRequestMonitor, PRStateRegistry


class TestGitHubMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = PullRequestMonitor(PRStateRegistry())

    def test_detect_changes_requested_alert(self):
        pr_initial = PullRequestSnapshot(
            repository="org/repo-core",
            number=50,
            title="feat: New billing engine",
            author="dev_user",
            html_url="https://github.com/org/repo-core/pull/50",
            head_branch="feature/billing",
            base_branch="main",
            head_sha="commit_sha_1",
            reviews=[],
            ci_status=CIStatus.SUCCESS,
            updated_at=datetime.now(timezone.utc),
        )
        alerts_t0 = self.monitor.evaluate_snapshot(pr_initial)
        self.assertEqual(len(alerts_t0), 0)

        # Reviewer requests changes
        pr_updated = pr_initial.model_copy(deep=True)
        pr_updated.reviews = [
            ReviewDetail(
                reviewer="lead_dev",
                state=ReviewState.CHANGES_REQUESTED,
                body="Please add idempotency key to prevent double charge.",
                html_url="https://github.com/org/repo-core/pull/50#review-1",
            )
        ]
        pr_updated.review_decision = "CHANGES_REQUESTED"

        alerts_t1 = self.monitor.evaluate_snapshot(pr_updated)
        self.assertEqual(len(alerts_t1), 1)
        self.assertEqual(alerts_t1[0].event_type, PRChangeType.PR_CHANGES_REQUESTED)
        self.assertEqual(alerts_t1[0].actor, "lead_dev")
        self.assertIn("idempotency key", alerts_t1[0].details)

    def test_detect_pr_approval_and_ready_for_merge(self):
        pr_initial = PullRequestSnapshot(
            repository="org/repo-core",
            number=51,
            title="fix: Patch memory leak in worker pool",
            author="dev_user",
            html_url="https://github.com/org/repo-core/pull/51",
            head_branch="fix/memory-leak",
            base_branch="main",
            head_sha="commit_sha_2",
            reviews=[],
            ci_status=CIStatus.PENDING,
            mergeable_state=MergeableState.CLEAN,
            updated_at=datetime.now(timezone.utc),
        )
        self.monitor.evaluate_snapshot(pr_initial)

        # Lead approves and CI passes
        pr_approved = pr_initial.model_copy(deep=True)
        pr_approved.reviews = [
            ReviewDetail(
                reviewer="lead_dev",
                state=ReviewState.APPROVED,
                body="Looks solid!",
                html_url="https://github.com/org/repo-core/pull/51#review-2",
            )
        ]
        pr_approved.review_decision = "APPROVED"
        pr_approved.ci_status = CIStatus.SUCCESS
        pr_approved.mergeable_state = MergeableState.CLEAN

        alerts = self.monitor.evaluate_snapshot(pr_approved)
        event_types = [a.event_type for a in alerts]
        self.assertIn(PRChangeType.PR_APPROVED, event_types)
        self.assertIn(PRChangeType.PR_READY_FOR_MERGE, event_types)

    def test_detect_ci_failure(self):
        pr_initial = PullRequestSnapshot(
            repository="org/repo-core",
            number=52,
            title="refactor: Upgrade dependencies",
            author="dev_user",
            html_url="https://github.com/org/repo-core/pull/52",
            head_branch="chore/deps",
            base_branch="main",
            head_sha="commit_sha_3",
            reviews=[],
            ci_status=CIStatus.PENDING,
            updated_at=datetime.now(timezone.utc),
        )
        self.monitor.evaluate_snapshot(pr_initial)

        # CI fails
        pr_failed = pr_initial.model_copy(deep=True)
        pr_failed.ci_status = CIStatus.FAILURE
        pr_failed.failing_checks = ["pytest-integration", "eslint"]

        alerts = self.monitor.evaluate_snapshot(pr_failed)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].event_type, PRChangeType.PR_CI_FAILED)
        self.assertIn("pytest-integration, eslint", alerts[0].details)


if __name__ == "__main__":
    unittest.main()
