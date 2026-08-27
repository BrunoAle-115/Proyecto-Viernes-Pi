"""
V.I.E.R.N.E.S GitHub API Service
Asynchronously fetches Pull Requests, reviews, check-runs, and merge status from GitHub REST API via httpx.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None

from src.config import settings
from src.github_monitor.models import (
    CheckRunDetail,
    CIStatus,
    MergeableState,
    PullRequestSnapshot,
    ReviewDetail,
    ReviewState,
)

logger = logging.getLogger("VIERNES.GitHubService")


class GitHubService:
    """
    Asynchronous client for interacting with GitHub REST API v3.
    """

    def __init__(
        self,
        access_token: Optional[str] = settings.GITHUB_ACCESS_TOKEN,
        base_url: str = "https://api.github.com",
    ):
        self.access_token = access_token
        self.base_url = base_url

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "VIERNES-Executive-Assistant",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def fetch_open_pull_requests(self, repository: str) -> List[PullRequestSnapshot]:
        """
        Fetches all open pull requests for a repository with detailed review and CI status.
        """
        if not httpx:
            logger.warning("httpx not installed; skipping live GitHub API fetch.")
            return []

        url = f"{self.base_url}/repos/{repository}/pulls?state=open&sort=updated&direction=desc&per_page=30"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    f"Failed to fetch PRs for repository '{repository}' (Status {resp.status_code}): {resp.text}"
                )
                return []
            pulls_data = resp.json()

            tasks = [self._enrich_pull_request(client, repository, pr_data) for pr_data in pulls_data]
            snapshots = await asyncio.gather(*tasks, return_exceptions=True)

            valid_snapshots: List[PullRequestSnapshot] = []
            for s in snapshots:
                if isinstance(s, PullRequestSnapshot):
                    valid_snapshots.append(s)
                elif isinstance(s, Exception):
                    logger.error(f"Error enriching PR: {s}")

            return valid_snapshots

    async def _enrich_pull_request(
        self, client: Any, repository: str, pr_data: Dict[str, Any]
    ) -> PullRequestSnapshot:
        """
        Enriches a single PR with review history and CI check suite runs.
        """
        headers = self._get_headers()
        pr_number = pr_data["number"]
        head_sha = pr_data["head"]["sha"]

        # Fetch reviews and check runs concurrently
        reviews_url = f"{self.base_url}/repos/{repository}/pulls/{pr_number}/reviews"
        checks_url = f"{self.base_url}/repos/{repository}/commits/{head_sha}/check-runs"

        reviews_res, checks_res = await asyncio.gather(
            client.get(reviews_url, headers=headers),
            client.get(checks_url, headers=headers),
            return_exceptions=True,
        )

        # Parse reviews
        parsed_reviews: List[ReviewDetail] = []
        if not isinstance(reviews_res, Exception) and reviews_res.status_code == 200:
            reviews_json = reviews_res.json()
            for r in reviews_json:
                state_str = r.get("state", "PENDING").upper()
                try:
                    r_state = ReviewState(state_str)
                except ValueError:
                    r_state = ReviewState.COMMENTED

                submitted_at_str = r.get("submitted_at")
                sub_dt = None
                if submitted_at_str:
                    try:
                        sub_dt = datetime.fromisoformat(submitted_at_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                parsed_reviews.append(
                    ReviewDetail(
                        reviewer=r.get("user", {}).get("login", "unknown"),
                        state=r_state,
                        submitted_at=sub_dt,
                        body=r.get("body", ""),
                        html_url=r.get("html_url"),
                    )
                )

        # Parse CI / Check Runs
        ci_status = CIStatus.UNKNOWN
        failing_checks: List[str] = []
        if not isinstance(checks_res, Exception) and checks_res.status_code == 200:
            checks_json = checks_res.json()
            check_runs = checks_json.get("check_runs", [])
            if check_runs:
                all_completed = all(cr.get("status") == "completed" for cr in check_runs)
                has_failure = any(
                    cr.get("conclusion") in ["failure", "timed_out", "action_required"]
                    for cr in check_runs
                )

                if has_failure:
                    ci_status = CIStatus.FAILURE
                    failing_checks = [
                        cr.get("name", "check")
                        for cr in check_runs
                        if cr.get("conclusion") in ["failure", "timed_out", "action_required"]
                    ]
                elif all_completed:
                    ci_status = CIStatus.SUCCESS
                else:
                    ci_status = CIStatus.PENDING

        # Requested reviewers
        requested_reviewers = [
            u.get("login") for u in pr_data.get("requested_reviewers", []) if u.get("login")
        ]

        # Mergeable state
        mergeable_raw = (pr_data.get("mergeable_state") or "unknown").lower()
        merge_map = {
            "clean": MergeableState.CLEAN,
            "dirty": MergeableState.DIRTY,
            "blocked": MergeableState.BLOCKED,
            "behind": MergeableState.BEHIND,
            "draft": MergeableState.DRAFT,
        }
        mergeable_state = merge_map.get(mergeable_raw, MergeableState.UNKNOWN)

        updated_at_str = pr_data.get("updated_at", "")
        updated_dt = datetime.now(timezone.utc)
        if updated_at_str:
            try:
                updated_dt = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            except Exception:
                pass

        # Compute review decision
        latest_reviews_by_user: Dict[str, ReviewState] = {}
        for r in parsed_reviews:
            if r.state in [ReviewState.APPROVED, ReviewState.CHANGES_REQUESTED, ReviewState.DISMISSED]:
                latest_reviews_by_user[r.reviewer] = r.state

        latest_states = list(latest_reviews_by_user.values())
        if ReviewState.CHANGES_REQUESTED in latest_states:
            review_decision = "CHANGES_REQUESTED"
        elif latest_states and all(s == ReviewState.APPROVED for s in latest_states):
            review_decision = "APPROVED"
        else:
            review_decision = "REVIEW_REQUIRED"

        return PullRequestSnapshot(
            repository=repository,
            number=pr_data["number"],
            title=pr_data.get("title", ""),
            author=pr_data.get("user", {}).get("login", ""),
            html_url=pr_data.get("html_url", ""),
            head_branch=pr_data.get("head", {}).get("ref", ""),
            base_branch=pr_data.get("base", {}).get("ref", ""),
            head_sha=head_sha,
            is_draft=pr_data.get("draft", False),
            review_decision=review_decision,
            reviews=parsed_reviews,
            requested_reviewers=requested_reviewers,
            ci_status=ci_status,
            failing_checks=failing_checks,
            mergeable=pr_data.get("mergeable"),
            mergeable_state=mergeable_state,
            updated_at=updated_dt,
        )
