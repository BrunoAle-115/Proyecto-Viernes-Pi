"""
Monitor de GitHub para V.I.E.R.N.E.S.
Monitorea Pull Requests (aprobados, cambios solicitados, mergeados), issues y GitHub Actions.
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("viernes.integrations.github")


class GitHubMonitor:
    def __init__(self, token: Optional[str] = None, repos: Optional[List[str]] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.username = os.getenv("GITHUB_USERNAME", "")
        repos_raw = os.getenv("GITHUB_REPOS", "")
        self.target_repos = repos or ([r.strip() for r in repos_raw.split(",") if r.strip()])
        self._github_client = None
        self._init_client()

    def _init_client(self):
        if not self.token or self.token.startswith("ghp_Your"):
            logger.debug("Token de GitHub no configurado. Modo Mock/Standby activo.")
            return
        try:
            from github import Github, Auth
            auth = Auth.Token(self.token)
            self._github_client = Github(auth=auth)
            logger.info("Cliente de GitHub autenticado correctamente.")
        except Exception as e:
            logger.error(f"Error inicializando cliente PyGithub: {e}")

    async def get_pull_requests_summary(self) -> Dict[str, Any]:
        """Consulta el estado de las PRs creadas o asignadas al usuario."""
        if not self._github_client:
            # Retorna datos de simulación si no hay token para pruebas fluidas
            return {
                "configured": False,
                "total_open": 1,
                "prs": [
                    {
                        "repo": "Proyecto-Viernes-Pi",
                        "number": 1,
                        "title": "feat(core): implementacion inicial de V.I.E.R.N.E.S. framework",
                        "status": "APPROVED",
                        "reviews_count": 2,
                        "approved_by": ["Stark-Reviewer"],
                        "ci_status": "SUCCESS",
                        "url": "https://github.com/tu_usuario/Proyecto-Viernes-Pi/pull/1",
                        "updated_at": datetime.now().isoformat(),
                    }
                ],
                "message": "GitHub en modo demo. Configura GITHUB_TOKEN en .env para datos en vivo.",
            }

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_fetch_prs)

    def _sync_fetch_prs(self) -> Dict[str, Any]:
        """Consulta síncrona en hilo separado para no bloquear el event loop."""
        try:
            prs_list = []
            # Si se especificaron repositorios específicos
            if self.target_repos:
                for repo_name in self.target_repos:
                    try:
                        repo = self._github_client.get_repo(repo_name)
                        for pr in repo.get_pulls(state="open"):
                            # Obtener reviews
                            reviews = list(pr.get_reviews())
                            approved_by = [r.user.login for r in reviews if r.state == "APPROVED"]
                            changes_requested = [r.user.login for r in reviews if r.state == "CHANGES_REQUESTED"]

                            state_str = "PENDING_REVIEW"
                            if changes_requested:
                                state_str = "CHANGES_REQUESTED"
                            elif approved_by:
                                state_str = "APPROVED"

                            prs_list.append({
                                "repo": repo_name,
                                "number": pr.number,
                                "title": pr.title,
                                "author": pr.user.login,
                                "status": state_str,
                                "approved_by": approved_by,
                                "changes_requested_by": changes_requested,
                                "url": pr.html_url,
                                "updated_at": pr.updated_at.isoformat() if pr.updated_at else "",
                            })
                    except Exception as repo_err:
                        logger.error(f"Error consultando repositorio {repo_name}: {repo_err}")

            return {
                "configured": True,
                "total_open": len(prs_list),
                "prs": prs_list,
                "summary": f"Tienes {len(prs_list)} Pull Requests abiertas."
            }
        except Exception as e:
            logger.error(f"Error global consultando GitHub: {e}")
            return {"configured": True, "total_open": 0, "prs": [], "error": str(e)}


github_monitor = GitHubMonitor()
