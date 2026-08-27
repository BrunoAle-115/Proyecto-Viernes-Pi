"""
V.I.E.R.N.E.S GitHub PR Monitor Engine & State Machine
Compares PR state snapshots over time to detect new Approvals, Requested Changes, CI breakages, and conflicts.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.github_monitor.models import (
    CIStatus,
    MergeableState,
    PRAlertEvent,
    PRChangeType,
    PullRequestSnapshot,
    ReviewDetail,
    ReviewState,
)

logger = logging.getLogger("VIERNES.PRMonitor")


class PRStateRegistry:
    """
    In-memory or persistent state store to track historical snapshots of PRs.
    """

    def __init__(self):
        self._snapshots: Dict[str, PullRequestSnapshot] = {}

    def get_key(self, repo: str, pr_number: int) -> str:
        return f"{repo}#{pr_number}"

    def get(self, repo: str, pr_number: int) -> Optional[PullRequestSnapshot]:
        return self._snapshots.get(self.get_key(repo, pr_number))

    def update(self, snapshot: PullRequestSnapshot):
        self._snapshots[self.get_key(snapshot.repository, snapshot.number)] = snapshot


class PullRequestMonitor:
    """
    Evaluates PR state transitions and generates structured alerts.
    """

    def __init__(self, registry: Optional[PRStateRegistry] = None):
        self.registry = registry or PRStateRegistry()

    def evaluate_snapshot(self, current: PullRequestSnapshot) -> List[PRAlertEvent]:
        """
        Compares current snapshot against previous state to generate alerts.
        """
        previous = self.registry.get(current.repository, current.number)
        alerts: List[PRAlertEvent] = []

        if not previous:
            # First time observing this PR: check if there are already pending action items
            alerts.extend(self._evaluate_initial_state(current))
            self.registry.update(current)
            return alerts

        # -------------------------------------------------------------
        # 1. Detect Review Changes (Approved / Changes Requested)
        # -------------------------------------------------------------
        prev_reviews_map = {r.reviewer: r for r in previous.reviews}
        for r in current.reviews:
            prev_r = prev_reviews_map.get(r.reviewer)

            # Check if this reviewer gave a new review or changed their vote
            if not prev_r or prev_r.state != r.state:
                if r.state == ReviewState.CHANGES_REQUESTED:
                    feedback_snip = f": \"{r.body[:180]}...\"" if r.body else "."
                    alerts.append(
                        PRAlertEvent(
                            event_type=PRChangeType.PR_CHANGES_REQUESTED,
                            repository=current.repository,
                            pr_number=current.number,
                            pr_title=current.title,
                            pr_url=r.html_url or current.html_url,
                            actor=r.reviewer,
                            headline=f"⚠️ Changes Requested on PR #{current.number} by @{r.reviewer}",
                            details=f"@{r.reviewer} requested changes on '{current.title}'{feedback_snip}",
                            action_required=True,
                            suggested_action=f"Address @{r.reviewer}'s review comments and re-request review.",
                        )
                    )

                elif r.state == ReviewState.APPROVED:
                    alerts.append(
                        PRAlertEvent(
                            event_type=PRChangeType.PR_APPROVED,
                            repository=current.repository,
                            pr_number=current.number,
                            pr_title=current.title,
                            pr_url=r.html_url or current.html_url,
                            actor=r.reviewer,
                            headline=f"✅ PR #{current.number} Approved by @{r.reviewer}",
                            details=f"@{r.reviewer} approved '{current.title}'.",
                            action_required=False,
                            suggested_action="Verify all checks pass before proceeding to merge.",
                        )
                    )

        # -------------------------------------------------------------
        # 2. Check if Entire PR is Ready for Merge
        # -------------------------------------------------------------
        if (
            current.review_decision == "APPROVED"
            and current.ci_status == CIStatus.SUCCESS
            and current.mergeable_state == MergeableState.CLEAN
            and (
                previous.review_decision != "APPROVED"
                or previous.ci_status != CIStatus.SUCCESS
            )
        ):
            alerts.append(
                PRAlertEvent(
                    event_type=PRChangeType.PR_READY_FOR_MERGE,
                    repository=current.repository,
                    pr_number=current.number,
                    pr_title=current.title,
                    pr_url=current.html_url,
                    actor="system",
                    headline=f"🚀 PR #{current.number} Ready to Merge!",
                    details=f"All reviews approved and CI passed successfully for '{current.title}'.",
                    action_required=True,
                    suggested_action="Review final diff and click Merge.",
                )
            )

        # -------------------------------------------------------------
        # 3. Detect CI Status Transitions
        # -------------------------------------------------------------
        if current.ci_status == CIStatus.FAILURE and previous.ci_status != CIStatus.FAILURE:
            failing_str = ", ".join(current.failing_checks) if current.failing_checks else "Unknown checks"
            alerts.append(
                PRAlertEvent(
                    event_type=PRChangeType.PR_CI_FAILED,
                    repository=current.repository,
                    pr_number=current.number,
                    pr_title=current.title,
                    pr_url=current.html_url,
                    actor="CI/GitHub Actions",
                    headline=f"❌ CI Checks Failed on PR #{current.number}",
                    details=f"Failing checks on '{current.title}': {failing_str}.",
                    action_required=True,
                    suggested_action="Inspect CI error logs and push fix commit.",
                )
            )

        # -------------------------------------------------------------
        # 4. Detect Merge Conflicts
        # -------------------------------------------------------------
        if current.mergeable_state == MergeableState.DIRTY and previous.mergeable_state != MergeableState.DIRTY:
            alerts.append(
                PRAlertEvent(
                    event_type=PRChangeType.PR_MERGE_CONFLICT,
                    repository=current.repository,
                    pr_number=current.number,
                    pr_title=current.title,
                    pr_url=current.html_url,
                    actor="git",
                    headline=f"💥 Merge Conflict in PR #{current.number}",
                    details=f"Branch '{current.head_branch}' has conflicts with base '{current.base_branch}'.",
                    action_required=True,
                    suggested_action=f"Rebase or merge '{current.base_branch}' into '{current.head_branch}' and resolve conflicts.",
                )
            )

        self.registry.update(current)
        return alerts

    def _evaluate_initial_state(self, current: PullRequestSnapshot) -> List[PRAlertEvent]:
        """Flags high-priority states on startup."""
        alerts: List[PRAlertEvent] = []
        if current.review_decision == "CHANGES_REQUESTED":
            reviewers = [r.reviewer for r in current.reviews if r.state == ReviewState.CHANGES_REQUESTED]
            alerts.append(
                PRAlertEvent(
                    event_type=PRChangeType.PR_CHANGES_REQUESTED,
                    repository=current.repository,
                    pr_number=current.number,
                    pr_title=current.title,
                    pr_url=current.html_url,
                    actor=", ".join(reviewers),
                    headline=f"⚠️ Pending Changes Requested on PR #{current.number}",
                    details=f"PR '{current.title}' currently has requested changes from {', '.join(reviewers)}.",
                    action_required=True,
                    suggested_action="Address open review feedback.",
                )
            )
        return alerts
