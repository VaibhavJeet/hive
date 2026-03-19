"""
Bot GitHub Integration.

Gives bots the ability to:
- Create and manage repositories
- Push and pull code
- Learn from code history
- Collaborate on projects
- Evolve their own codebase

This is where bots become truly autonomous developers.
"""

import os
import json
import logging
import base64
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from dataclasses import dataclass, field
import aiohttp

from mind.config.settings import settings
from mind.core.types import BotProfile
from mind.core.llm_client import get_cached_client, LLMRequest

logger = logging.getLogger(__name__)


@dataclass
class GitHubRepo:
    """Represents a GitHub repository."""
    name: str
    full_name: str
    description: str
    url: str
    clone_url: str
    default_branch: str = "main"
    is_private: bool = True
    created_at: Optional[str] = None


@dataclass
class GitHubFile:
    """Represents a file in a repository."""
    path: str
    content: str
    sha: Optional[str] = None
    encoding: str = "utf-8"


@dataclass
class GitHubCommit:
    """Represents a commit."""
    sha: str
    message: str
    author: str
    date: str
    files_changed: List[str] = field(default_factory=list)


class BotGitHubClient:
    """
    GitHub client for a single bot.
    Allows bots to interact with GitHub as autonomous developers.
    """

    def __init__(self, bot: BotProfile, token: str):
        self.bot = bot
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"BotDeveloper-{bot.display_name}"
        }
        self.owned_repos: Dict[str, GitHubRepo] = {}

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        raw_content: bool = False
    ) -> Tuple[int, Any]:
        """Make an authenticated request to GitHub API."""
        url = f"{self.base_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            kwargs = {"headers": self.headers}
            if data:
                kwargs["json"] = data

            async with session.request(method, url, **kwargs) as response:
                status = response.status
                if raw_content:
                    content = await response.text()
                else:
                    try:
                        content = await response.json()
                    except:
                        content = await response.text()
                return status, content

    # =========================================================================
    # REPOSITORY OPERATIONS
    # =========================================================================

    async def create_repo(
        self,
        name: str,
        description: str,
        private: bool = True,
        auto_init: bool = True
    ) -> Optional[GitHubRepo]:
        """Create a new repository."""
        # Sanitize repo name
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower())

        data = {
            "name": safe_name,
            "description": f"{description} (by {self.bot.display_name})",
            "private": private,
            "auto_init": auto_init
        }

        status, response = await self._request("POST", "/user/repos", data)

        if status == 201:
            repo = GitHubRepo(
                name=response["name"],
                full_name=response["full_name"],
                description=response.get("description", ""),
                url=response["html_url"],
                clone_url=response["clone_url"],
                default_branch=response.get("default_branch", "main"),
                is_private=response["private"],
                created_at=response["created_at"]
            )
            self.owned_repos[repo.name] = repo
            logger.info(f"Bot {self.bot.display_name} created repo: {repo.full_name}")
            return repo
        else:
            logger.error(f"Failed to create repo: {response}")
            return None

    async def list_repos(self) -> List[GitHubRepo]:
        """List all repositories accessible to the bot."""
        status, response = await self._request("GET", "/user/repos?per_page=100")

        if status == 200:
            repos = []
            for r in response:
                repo = GitHubRepo(
                    name=r["name"],
                    full_name=r["full_name"],
                    description=r.get("description", ""),
                    url=r["html_url"],
                    clone_url=r["clone_url"],
                    default_branch=r.get("default_branch", "main"),
                    is_private=r["private"]
                )
                repos.append(repo)
                self.owned_repos[repo.name] = repo
            return repos
        return []

    async def get_repo(self, owner: str, repo_name: str) -> Optional[GitHubRepo]:
        """Get a specific repository."""
        status, response = await self._request("GET", f"/repos/{owner}/{repo_name}")

        if status == 200:
            return GitHubRepo(
                name=response["name"],
                full_name=response["full_name"],
                description=response.get("description", ""),
                url=response["html_url"],
                clone_url=response["clone_url"],
                default_branch=response.get("default_branch", "main"),
                is_private=response["private"]
            )
        return None

    async def delete_repo(self, owner: str, repo_name: str) -> bool:
        """Delete a repository."""
        status, _ = await self._request("DELETE", f"/repos/{owner}/{repo_name}")
        if status == 204:
            if repo_name in self.owned_repos:
                del self.owned_repos[repo_name]
            logger.info(f"Bot {self.bot.display_name} deleted repo: {owner}/{repo_name}")
            return True
        return False

    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================

    async def get_file(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str = "main"
    ) -> Optional[GitHubFile]:
        """Get a file from a repository."""
        status, response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        )

        if status == 200 and response.get("type") == "file":
            content = base64.b64decode(response["content"]).decode("utf-8")
            return GitHubFile(
                path=path,
                content=content,
                sha=response["sha"]
            )
        return None

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: Optional[str] = None
    ) -> bool:
        """Create or update a file in a repository."""
        # If updating, we need the current SHA
        if not sha:
            existing = await self.get_file(owner, repo, path, branch)
            if existing:
                sha = existing.sha

        data = {
            "message": f"{message} (by {self.bot.display_name})",
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch
        }
        if sha:
            data["sha"] = sha

        status, response = await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{path}",
            data
        )

        if status in [200, 201]:
            logger.info(f"Bot {self.bot.display_name} updated {path} in {owner}/{repo}")
            return True
        else:
            logger.error(f"Failed to update file: {response}")
            return False

    async def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        branch: str = "main"
    ) -> bool:
        """Delete a file from a repository."""
        existing = await self.get_file(owner, repo, path, branch)
        if not existing:
            return False

        data = {
            "message": f"{message} (by {self.bot.display_name})",
            "sha": existing.sha,
            "branch": branch
        }

        status, _ = await self._request(
            "DELETE",
            f"/repos/{owner}/{repo}/contents/{path}",
            data
        )
        return status == 200

    async def list_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
        branch: str = "main"
    ) -> List[Dict]:
        """List files in a directory."""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        status, response = await self._request("GET", endpoint)

        if status == 200 and isinstance(response, list):
            return [
                {
                    "name": f["name"],
                    "path": f["path"],
                    "type": f["type"],
                    "sha": f["sha"]
                }
                for f in response
            ]
        return []

    # =========================================================================
    # HISTORY & LEARNING
    # =========================================================================

    async def get_commits(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        limit: int = 30
    ) -> List[GitHubCommit]:
        """Get commit history for a repository."""
        status, response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits?sha={branch}&per_page={limit}"
        )

        if status == 200:
            commits = []
            for c in response:
                commits.append(GitHubCommit(
                    sha=c["sha"][:7],
                    message=c["commit"]["message"],
                    author=c["commit"]["author"]["name"],
                    date=c["commit"]["author"]["date"],
                    files_changed=[]  # Would need another API call
                ))
            return commits
        return []

    async def get_commit_details(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> Optional[Dict]:
        """Get detailed information about a specific commit."""
        status, response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{sha}"
        )

        if status == 200:
            return {
                "sha": response["sha"],
                "message": response["commit"]["message"],
                "author": response["commit"]["author"]["name"],
                "date": response["commit"]["author"]["date"],
                "files": [
                    {
                        "filename": f["filename"],
                        "status": f["status"],
                        "additions": f["additions"],
                        "deletions": f["deletions"],
                        "patch": f.get("patch", "")[:500]  # Limit patch size
                    }
                    for f in response.get("files", [])[:10]  # Limit files
                ]
            }
        return None

    async def learn_from_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Analyze a repository to learn from it.
        Returns insights about code patterns, structure, and history.
        """
        insights = {
            "repo": f"{owner}/{repo}",
            "files": [],
            "languages": {},
            "patterns": [],
            "recent_changes": []
        }

        # Get file structure
        files = await self.list_files(owner, repo)
        insights["files"] = [f["name"] for f in files[:20]]

        # Analyze file types
        for f in files:
            ext = f["name"].split(".")[-1] if "." in f["name"] else "unknown"
            insights["languages"][ext] = insights["languages"].get(ext, 0) + 1

        # Get recent commits to understand changes
        commits = await self.get_commits(owner, repo, limit=10)
        insights["recent_changes"] = [
            {"message": c.message, "author": c.author, "date": c.date}
            for c in commits[:5]
        ]

        # Try to read key files
        key_files = ["README.md", "main.py", "index.js", "app.py", "package.json"]
        for key_file in key_files:
            if any(f["name"] == key_file for f in files):
                content = await self.get_file(owner, repo, key_file)
                if content:
                    insights["patterns"].append({
                        "file": key_file,
                        "preview": content.content[:500]
                    })
                    break

        return insights

    # =========================================================================
    # AUTONOMOUS DEVELOPMENT
    # =========================================================================

    async def develop_feature(
        self,
        owner: str,
        repo: str,
        feature_description: str
    ) -> Dict[str, Any]:
        """
        Autonomously develop a feature for a repository.
        The bot will:
        1. Analyze the existing code
        2. Plan the feature
        3. Write the code
        4. Commit it
        """
        result = {
            "success": False,
            "files_created": [],
            "files_modified": [],
            "commit_message": ""
        }

        # First, learn about the repo
        insights = await self.learn_from_repo(owner, repo)

        # Use LLM to plan and write code
        try:
            llm = await get_cached_client()

            prompt = f"""You are {self.bot.display_name}, a developer bot.

## REPOSITORY: {owner}/{repo}
Files: {', '.join(insights['files'][:10])}
Languages: {insights['languages']}

## EXISTING CODE PATTERNS
{json.dumps(insights['patterns'][:2], indent=2) if insights['patterns'] else 'No patterns analyzed'}

## RECENT CHANGES
{json.dumps(insights['recent_changes'][:3], indent=2)}

## FEATURE TO DEVELOP
{feature_description}

## YOUR TASK
1. Decide what file(s) to create or modify
2. Write the actual code
3. Provide a commit message

Output format (JSON):
{{
    "files": [
        {{"path": "filename.py", "content": "actual code here", "action": "create|modify"}}
    ],
    "commit_message": "feat: description of what was done"
}}
"""

            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.7
            ))

            # Parse the response
            text = response.text
            # Find JSON block
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            else:
                json_str = text

            plan = json.loads(json_str.strip())

            # Execute the plan
            for file_info in plan.get("files", []):
                path = file_info["path"]
                content = file_info["content"]
                action = file_info.get("action", "create")

                success = await self.create_or_update_file(
                    owner, repo, path, content,
                    message=plan.get("commit_message", f"Update {path}")
                )

                if success:
                    if action == "create":
                        result["files_created"].append(path)
                    else:
                        result["files_modified"].append(path)

            result["success"] = len(result["files_created"]) + len(result["files_modified"]) > 0
            result["commit_message"] = plan.get("commit_message", "")

            logger.info(f"Bot {self.bot.display_name} developed feature: {result}")

        except Exception as e:
            logger.error(f"Feature development failed: {e}")
            result["error"] = str(e)

        return result

    async def improve_self(self, self_repo: str) -> Dict[str, Any]:
        """
        The bot improves its own codebase.
        This is meta-level self-improvement through GitHub.
        """
        # This would modify the bot's own code in a designated repo
        # For safety, this should be carefully controlled

        result = await self.develop_feature(
            owner=self_repo.split("/")[0],
            repo=self_repo.split("/")[1],
            feature_description=f"""
            Analyze the current bot code and suggest one small improvement.
            Focus on:
            - Code clarity
            - Better patterns
            - Bug fixes
            - Performance improvements
            Only make ONE small, safe change.
            """
        )
        return result


# =============================================================================
# GITHUB MANAGER
# =============================================================================

class GitHubManager:
    """Manages GitHub clients for all bots."""

    def __init__(self):
        self.clients: Dict[UUID, BotGitHubClient] = {}
        self.token: Optional[str] = None

    def set_token(self, token: str):
        """Set the GitHub token for all bots."""
        self.token = token

    def get_client(self, bot: BotProfile) -> Optional[BotGitHubClient]:
        """Get or create a GitHub client for a bot."""
        if not self.token:
            logger.warning("GitHub token not set")
            return None

        if bot.id not in self.clients:
            self.clients[bot.id] = BotGitHubClient(bot, self.token)
        return self.clients[bot.id]

    async def get_username(self) -> Optional[str]:
        """Get the authenticated GitHub username."""
        if not self.token:
            return None

        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.github.com/user", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("login")
        return None


# Singleton
_github_manager: Optional[GitHubManager] = None


def get_github_manager() -> GitHubManager:
    """Get the singleton GitHub manager."""
    global _github_manager
    if _github_manager is None:
        _github_manager = GitHubManager()
    return _github_manager
