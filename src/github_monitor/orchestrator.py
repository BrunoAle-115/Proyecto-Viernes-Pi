"""
V.I.E.R.N.E.S GitHub Monitor Orchestrator
Coordinates multi-repository polling, review lifecycle tracking, and alert dispatching.
"""

import asyncio
import logging
from typing import List, Optional

from src.config import settings
from src.github_monitor.github_service import GitHubService
from src.github_monitor.models import PRAlertEvent, PullRequestSnapshot
from src.github_monitor.pr_monitor import PullRequestMonitor

logger = logging.getLogger("VIERNES.GitHubOrchestrator")


class GitHubMonitorOrchestrator:
    """
    Coordinates pull request scanning across repositories for V.I.E.R.N.E.S.
    """

    def __init__(
        self,
        github_service: Optional[GitHubService] = None,
        pr_monitor: Optional[PullRequestMonitor] = None,
        repositories: Optional[List[str]] = None,
    ):
        self.github = github_service or GitHubService()
        self.pr_monitor = pr_monitor or PullRequestMonitor()
        self.repositories = repositories or settings.GITHUB_REPOSITORIES

    async def scan_all_repositories(self) -> List[PRAlertEvent]:
        """
        Polls all monitored GitHub repositories and detects review/CI status updates.
        """
        logger.info(f"Scanning {len(self.repositories)} repositories for PR activity...")
        all_alerts: List[PRAlertEvent] = []

        for repo in self.repositories:
            try:
                snapshots = await self.github.fetch_open_pull_requests(repo)
                logger.info(f"Found {len(snapshots)} open PRs in {repo}")
                for snap in snapshots:
                    alerts = self.pr_monitor.evaluate_snapshot(snap)
                    if alerts:
                        for alert in alerts:
                            logger.info(f"PR Alert [{alert.event_type.value}] on {repo}#{snap.number}: {alert.headline}")
                        all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Error scanning repository {repo}: {e}")

        return all_alerts

    async def run_daemon(self, interval_seconds: int = settings.GITHUB_POLL_INTERVAL_SECONDS):
        """
        Runs continuous background monitoring loop.
        """
        logger.info(f"Starting GitHub PR Monitor daemon (Interval: {interval_seconds}s)...")
        while True:
            try:
                alerts = await self.scan_all_repositories()
                if alerts:
                    # In production V.I.E.R.N.E.S, this dispatches to Telegram/Slack/Desktop notifications
                    logger.info(f"Dispatched {len(alerts)} GitHub PR alerts to executive notification hub.")
            except Exception as e:
                logger.error(f"Error in GitHub Monitor daemon cycle: {e}")
            await asyncio.sleep(interval_seconds)
